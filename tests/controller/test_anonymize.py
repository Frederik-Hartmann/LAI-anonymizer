# UNIT TESTS for controller/anonymize.py
# use pytest from terminal to show full logging output

import os
import pytest
from copy import deepcopy
import logging
from pathlib import Path
from queue import Queue
from time import sleep

import csv
from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.dataset import Dataset, FileDataset
from pydicom.tag import Tag

from anonymizer.controller.anonymizer import AnonymizerController, QuarantineDirectories
from anonymizer.controller.project import ProjectController, ProjectModel
from tests.controller.dicom_test_files import (
    cr1_filename,
    ct_small_filename,
    mr_brain_filename,
    # mr_small_filename,
    # mr_small_implicit_filename,
    # mr_small_bigendian_filename,
    CR_STUDY_3_SERIES_3_IMAGES,
    # CT_STUDY_1_SERIES_4_IMAGES,
    MR_STUDY_3_SERIES_11_IMAGES,
)
from tests.controller.dicom_test_nodes import LocalSCU


# Test a valid date before 19000101
def test_valid_date_before_19000101(controller):
    anon = controller.anonymizer
    input_date = "18991231"
    assert not anon.valid_date(input_date)
    assert anon._hash_date(input_date, "12345") == (0, anon.DEFAULT_ANON_DATE)


# Test a valid date on or after 19000101
def test_valid_date_on_or_after_19000101(controller):
    anon = controller.anonymizer
    assert anon.valid_date("19010101")
    assert anon.valid_date("19801228")
    assert anon.valid_date("19660307")
    assert anon.valid_date("20231212")
    assert anon.valid_date("20220101")


# Test an invalid date format
def test_invalid_date_format(controller):
    anon = controller.anonymizer
    assert not anon.valid_date("01-01-2022")
    assert not anon.valid_date("2001-01-02")
    assert not anon.valid_date("01/01/2022")
    assert not anon.valid_date("0101192")


# Test an invalid date value (not a valid date)
def test_invalid_date_value(controller):
    anon = controller.anonymizer
    assert not anon.valid_date("20220230")
    assert not anon.valid_date("20220231")
    assert not anon.valid_date("20220431")
    assert not anon.valid_date("20220631")
    assert not anon.valid_date("99991232")


# Test with a known date and PatientID
def test_valid_date_hashing(controller):
    anon = controller.anonymizer
    assert "20220921" == anon._hash_date("20220101", "12345")[1]
    assert "20250815" == anon._hash_date("20220101", "67890")[1]
    assert "19080814" == anon._hash_date("19000101", "123456789")[1]
    assert "19080412" == anon._hash_date("19000101", "1234567890")[1]


def test_valid_date_hash_patient_id_range(controller):
    anon = controller.anonymizer
    for i in range(100):
        _, hdate = anon._hash_date("20100202", str(i))
        assert anon.valid_date(hdate)


def test_valid_time(controller):
    anon = controller.anonymizer
    # valid hour only formats
    assert anon.valid_time("00") == True
    assert anon.valid_time("11") == True
    assert anon.valid_time("23") == True

    # invalid hour only format 
    assert anon.valid_time("24") == False
    assert anon.valid_time("2") == False

    # valid hour, minute format
    assert anon.valid_time("0000") == True
    assert anon.valid_time("0023") == True
    assert anon.valid_time("0059") == True

    # invalid hour, minute format
    assert anon.valid_time("0060") == False
    assert anon.valid_time("0099") == False
    assert anon.valid_time("005") == False
    assert anon.valid_time("00.00") == False
    assert anon.valid_time("00,00") == False

    # valid hour, minute, second formats
    assert anon.valid_time("000000") == True
    assert anon.valid_time("000023") == True
    assert anon.valid_time("000059") == True
    assert anon.valid_time("000060") == True # leap second

    # invalid hour, minute, second formats
    assert anon.valid_time("000061") == False
    assert anon.valid_time("00005") == False
    assert anon.valid_time("000099") == False
    assert anon.valid_time("00.00.00") == False
    assert anon.valid_time("00,00,00") == False

    # valid hour, minute, second, fraction formats
    assert anon.valid_time("000000.000000") == True
    assert anon.valid_time("000000.123456") == True
    assert anon.valid_time("000000.456789") == True
    assert anon.valid_time("000000.999999") == True
    assert anon.valid_time("000000.00000") == True
    assert anon.valid_time("000000.0000") == True
    assert anon.valid_time("000000.000") == True
    assert anon.valid_time("000000.00") == True
    assert anon.valid_time("000000.0") == True

    # invalid hour, minute, second, fraction formats
    assert anon.valid_time("000000.0000000") == False
    assert anon.valid_time("000000.") == False
    assert anon.valid_time("000000,000000") == False

    # leading, embedded and trailing spaces
    assert anon.valid_time(" 000000.000000") == False
    assert anon.valid_time("00 0000.000000") == False
    assert anon.valid_time("000000.000000 ") == True

@pytest.mark.parametrize(
    "date, operation, expected_days, expected_result",
    [
        # Normal expected cases
        ("20220415", "2022,1,1", -104, "20220101"),
        ("20220415", "this,*,1,1", -104, "20220101"),
        ("20220415", "*,*,*,1", -14, "20220401"),
        ("20220415", "2023,*,*", 365, "20230415"),

        # Missing "this" elementname (implicitly assumes "this")
        ("20220115", "*,1,1", -14, "20220101"),
        ("20220115", "2023,*,1", 351, "20230101"),

        # Invalid input date format
        ("badinput", "2022,1,1", 0, "USE_DEFAULT"),

        # Invalid values in operation
        ("20220115", "foo,1,1", 0, "USE_DEFAULT"),
        ("20220115", "2022,2,30", 0, "USE_DEFAULT"),

        # Too few or too many operation arguments
        ("20220115", "this,1", 0, "USE_DEFAULT"),
        ("20220115", "1,1,1,1,1", 0, "USE_DEFAULT"),

        # Empty operation
        ("20220115", "", 0, "USE_DEFAULT"),
    ]
)
def test_modify_date(controller, date, operation, expected_days, expected_result):
    result = controller.anonymizer._modify_date(date, operation)
    if expected_result == "USE_DEFAULT":
        default_anon_date = controller.anonymizer.DEFAULT_ANON_DATE
        assert result == (0, default_anon_date)
    else:
        assert result == (expected_days, expected_result)

@pytest.mark.parametrize(
    "processed_operation, expected_result",
    [
        # Normal expected cases (date in file=20010101)
        ("2022,11,14", "20221114"),
        ("this,*,3,5", "20010305"),
        ("*,*,*,5", "20010105"),
        ("2023,*,*", "20230101"),
    ]
)
def test_modify_date_in_script(temp_dir, processed_operation, expected_result):
    # create custom script and init anonymizer
    script_path = Path(temp_dir) / "custom.script"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(
        f"""<script>
<e en="T" t="00080022" n="AcquisitionDate">@modifydate({processed_operation})</e>
<e en="T" t="00080016" n="SOPClassUID">@hashuid</e>
<e en="T" t="00080018" n="SOPInstanceUID">@hashuid</e>
<e en="T" t="0020000D" n="StudyInstanceUID">@hashuid</e>
<e en="T" t="0020000E" n="SeriesInstanceUID">@hashuid</e>
</script>"""
    )
    model = ProjectModel(anonymizer_script_path=script_path, storage_dir=Path(temp_dir, LocalSCU.aet))
    controller = ProjectController(model)

    # run anonymizer
    cr1 : FileDataset= get_testdata_file(cr1_filename, read=True)
    test_filename = "test.dcm" # AcquisitionDate = 20010101
    test_dcm_file_path = Path(temp_dir, test_filename)
    cr1.save_as(test_dcm_file_path)
    error_msg, ds = controller.anonymizer.anonymize_file(test_dcm_file_path)
    controller.anonymizer.stop()

    # test if tag "AcquisitionDate" is modified
    assert ds[0x00080022].value == expected_result

def test_valid_time_hash_patient_id_range(controller):
    anon = controller.anonymizer
    for i in range(100):
        _, htime = anon._hash_time("123456.123456", str(i))
        assert anon.valid_time(htime)

def test_hash_time_order_preserving(controller):
    # within bounds only (at least 2 seconds or 2 fractional seconds apart)
    anon = controller.anonymizer
    assert float(anon._hash_time("000000", "Patient-ID")[1]) < float(anon._hash_time("000002", "Patient-ID")[1]) # min 2 second apart
    assert float(anon._hash_time("000000", "Patient-ID")[1]) < float(anon._hash_time("000000.000001", "Patient-ID")[1]) # or frac precision
    assert float(anon._hash_time("180000", "Patient-ID")[1]) < float(anon._hash_time("230000", "Patient-ID")[1]) # 23:00:00 has midnight rollover, 18:00:00 not.
    assert float(anon._hash_time("000000.12", "Patient-ID")[1]) < float(anon._hash_time("000000.24", "Patient-ID")[1]) 
    assert float(anon._hash_time("000000.000000", "Patient-ID")[1]) < float(anon._hash_time("000000.000002", "Patient-ID")[1])


def test_anonymize_dataset_without_PatientID(temp_dir: str, controller):
    anonymizer: AnonymizerController = controller.anonymizer
    ds = get_testdata_file(cr1_filename, read=True)
    assert isinstance(ds, Dataset)
    assert ds
    assert ds.PatientID
    # Remove PatientID field
    del ds.PatientID
    phi_ds = deepcopy(ds)
    anonymizer.anonymize_dataset_ex(LocalSCU, ds)
    sleep(0.5)
    store_dir = controller.model.images_dir()
    dirlist = [d for d in os.listdir(store_dir) if os.path.isdir(os.path.join(store_dir, d))]

    SITEID = controller.model.site_id
    UIDROOT = controller.model.uid_root

    anon_pt_id = SITEID + "-000000"
    assert len(dirlist) == 1
    assert dirlist[0] == anon_pt_id
    anon_filename = anonymizer.local_storage_path(store_dir, ds)
    anon_ds = dcmread(anon_filename)
    assert isinstance(anon_ds, Dataset)
    assert anon_ds.PatientID == anon_pt_id
    assert anon_ds.PatientName == anon_pt_id
    assert anon_ds.AccessionNumber == "1"
    assert anon_ds.StudyDate != phi_ds.StudyDate
    assert anon_ds.StudyDate == anonymizer.DEFAULT_ANON_DATE
    assert anon_ds.SOPClassUID == phi_ds.SOPClassUID

    assert anon_ds.StudyInstanceUID == f"{UIDROOT}.{SITEID}.1"
    assert anon_ds.SeriesInstanceUID == f"{UIDROOT}.{SITEID}.2"
    assert anon_ds.SOPInstanceUID == f"{UIDROOT}.{SITEID}.3"
    assert controller.anonymizer.model.get_phi_name(anon_pt_id) == ""
    assert controller.anonymizer.model.get_phi(anon_pt_id).patient_id == ""


def test_anonymize_dataset_with_blank_PatientID_1_study(temp_dir: str, controller):
    anonymizer: AnonymizerController = controller.anonymizer
    ds1 = get_testdata_file(cr1_filename, read=True)
    assert isinstance(ds1, Dataset)
    assert ds1
    assert ds1.PatientID
    # Set Blank PatientID
    ds1.PatientID = ""
    phi_ds1 = deepcopy(ds1)
    anonymizer.anonymize_dataset_ex(LocalSCU, ds1)
    sleep(0.5)

    ds2 = get_testdata_file(ct_small_filename, read=True)
    assert isinstance(ds2, Dataset)
    assert ds2
    assert ds2.PatientID
    # Delete PatientID attribute
    del ds2.PatientID
    phi_ds2 = deepcopy(ds2)
    anonymizer.anonymize_dataset_ex(LocalSCU, ds2)

    sleep(0.5)
    store_dir = controller.model.images_dir()
    dirlist = [d for d in os.listdir(store_dir) if os.path.isdir(os.path.join(store_dir, d))]

    SITEID = controller.model.site_id
    UIDROOT = controller.model.uid_root

    # 1 Patient directory with 2 Studies:
    anon_pt_id = SITEID + "-000000"
    assert len(dirlist) == 1
    assert dirlist[0] == anon_pt_id

    anon_filename1 = anonymizer.local_storage_path(store_dir, ds1)
    anon_ds1 = dcmread(anon_filename1)
    assert isinstance(anon_ds1, Dataset)
    assert anon_ds1.PatientID == anon_pt_id
    assert anon_ds1.PatientName == anon_pt_id
    assert anon_ds1.AccessionNumber == "1"
    assert anon_ds1.StudyDate != phi_ds1.StudyDate
    assert anon_ds1.StudyDate == anonymizer.DEFAULT_ANON_DATE
    assert anon_ds1.SOPClassUID == phi_ds1.SOPClassUID
    assert anon_ds1.file_meta.TransferSyntaxUID == phi_ds1.file_meta.TransferSyntaxUID
    assert f"{UIDROOT}.{SITEID}." in anon_ds1.StudyInstanceUID
    assert f"{UIDROOT}.{SITEID}." in anon_ds1.SeriesInstanceUID
    assert f"{UIDROOT}.{SITEID}." in anon_ds1.SOPInstanceUID

    anon_filename2 = anonymizer.local_storage_path(store_dir, ds2)
    anon_ds2 = dcmread(anon_filename2)
    assert isinstance(anon_ds2, Dataset)
    assert anon_ds2.PatientID == anon_pt_id
    assert anon_ds2.PatientName == anon_pt_id
    assert anon_ds2.AccessionNumber == "2"
    assert anon_ds2.StudyDate != phi_ds2.StudyDate
    assert anon_ds2.StudyDate == anonymizer.DEFAULT_ANON_DATE
    assert anon_ds2.SOPClassUID == phi_ds2.SOPClassUID
    assert anon_ds2.file_meta.TransferSyntaxUID == phi_ds2.file_meta.TransferSyntaxUID
    assert f"{UIDROOT}.{SITEID}." in anon_ds2.StudyInstanceUID
    assert f"{UIDROOT}.{SITEID}." in anon_ds2.SeriesInstanceUID
    assert f"{UIDROOT}.{SITEID}." in anon_ds2.SOPInstanceUID

    anon_pt_dir = Path(store_dir, anon_pt_id).as_posix()
    anon_ptid_dirlist = [d for d in os.listdir(anon_pt_dir) if os.path.isdir(os.path.join(anon_pt_dir, d))]
    assert len(anon_ptid_dirlist) == 2
    assert anon_ds1.StudyInstanceUID in anon_ptid_dirlist
    assert anon_ds2.StudyInstanceUID in anon_ptid_dirlist

    assert controller.anonymizer.model.get_phi_name(anon_pt_id) == ""
    assert controller.anonymizer.model.get_phi(anon_pt_id).patient_id == ""


def test_anonymize_dataset_with_blank_PatientID_2_studies(temp_dir: str, controller):
    anonymizer: AnonymizerController = controller.anonymizer
    ds = get_testdata_file(cr1_filename, read=True)
    assert isinstance(ds, Dataset)
    assert ds
    assert ds.PatientID
    # Set Blank PatientID
    ds.PatientID = ""
    phi_ds = deepcopy(ds)
    anonymizer.anonymize_dataset_ex(LocalSCU, ds)
    sleep(0.5)
    store_dir = controller.model.images_dir()
    dirlist = [d for d in os.listdir(store_dir) if os.path.isdir(os.path.join(store_dir, d))]

    SITEID = controller.model.site_id
    UIDROOT = controller.model.uid_root

    anon_pt_id = SITEID + "-000000"
    assert len(dirlist) == 1
    assert dirlist[0] == anon_pt_id
    anon_filename = anonymizer.local_storage_path(store_dir, ds)
    anon_ds = dcmread(anon_filename)
    assert isinstance(anon_ds, Dataset)
    assert anon_ds.PatientID == anon_pt_id
    assert anon_ds.PatientName == anon_pt_id
    assert anon_ds.AccessionNumber == "1"
    assert anon_ds.StudyDate != phi_ds.StudyDate
    assert anon_ds.StudyDate == anonymizer.DEFAULT_ANON_DATE
    assert anon_ds.SOPClassUID == phi_ds.SOPClassUID
    assert anon_ds.StudyInstanceUID == f"{UIDROOT}.{SITEID}.1"
    assert anon_ds.SeriesInstanceUID == f"{UIDROOT}.{SITEID}.2"
    assert anon_ds.SOPInstanceUID == f"{UIDROOT}.{SITEID}.3"
    assert controller.anonymizer.model.get_phi_name(anon_pt_id) == ""
    assert controller.anonymizer.model.get_phi(anon_pt_id).patient_id == ""


def test_anonymize_dataset_with_PatientID(temp_dir: str, controller):
    anonymizer: AnonymizerController = controller.anonymizer
    ds = get_testdata_file(cr1_filename, read=True)
    assert isinstance(ds, Dataset)
    assert ds
    assert ds.PatientID
    phi_ds = deepcopy(ds)
    anonymizer.anonymize_dataset_ex(LocalSCU, ds)
    sleep(0.5)
    store_dir = controller.model.images_dir()
    dirlist = [d for d in os.listdir(store_dir) if os.path.isdir(os.path.join(store_dir, d))]

    SITEID = controller.model.site_id
    UIDROOT = controller.model.uid_root

    anon_pt_id = SITEID + "-000001"
    assert len(dirlist) == 1
    assert dirlist[0] == anon_pt_id
    anon_filename = anonymizer.local_storage_path(store_dir, ds)
    anon_ds = dcmread(anon_filename)
    assert isinstance(anon_ds, Dataset)
    assert anon_ds.PatientID == anon_pt_id
    assert anon_ds.PatientID != phi_ds.PatientID
    assert anon_ds.PatientName == anon_pt_id
    assert anon_ds.AccessionNumber == "1"
    assert anon_ds.StudyDate != phi_ds.StudyDate
    assert anon_ds.StudyDate == anonymizer._hash_date(phi_ds.StudyDate, phi_ds.PatientID)[1]
    assert anon_ds.SOPClassUID == phi_ds.SOPClassUID
    assert anon_ds.StudyInstanceUID == f"{UIDROOT}.{SITEID}.1"
    assert anon_ds.SeriesInstanceUID == f"{UIDROOT}.{SITEID}.2"
    assert anon_ds.SOPInstanceUID == f"{UIDROOT}.{SITEID}.3"


# QUARANTINE Tests:
def test_anonymize_file_not_found(temp_dir: str, controller: ProjectController):
    anonymizer: AnonymizerController = controller.anonymizer

    error_msg, ds = anonymizer.anonymize_file(Path("unknown_file.dcm"))

    assert error_msg
    assert "No such file" in error_msg
    assert ds is None

    error_msg, ds = anonymizer.anonymize_file(Path(temp_dir))

    assert error_msg
    assert "Is a directory" in error_msg or "Permission denied" in error_msg or "Errno 13" in error_msg
    assert ds is None


def test_anonymize_invalid_dicom_file(temp_dir: str, controller: ProjectController):
    anonymizer: AnonymizerController = controller.anonymizer

    test_filename = "test_file.txt"
    test_file_path = Path(temp_dir, test_filename)
    with open(test_file_path, "w") as f:
        f.write("Testing Anonymizer")

    error_msg, ds = anonymizer.anonymize_file(test_file_path)

    assert error_msg
    assert "File is missing DICOM File Meta" in error_msg
    assert ds is None

    # Ensure file is moved to correct quarantine directory:
    qpath = Path(anonymizer.get_quarantine_path(), QuarantineDirectories.INVALID_DICOM.value)
    assert qpath.exists()


def test_anonymize_dicom_missing_attributes(temp_dir: str, controller: ProjectController):
    anonymizer: AnonymizerController = controller.anonymizer

    cr1 = get_testdata_file(cr1_filename, read=True)
    assert isinstance(cr1, Dataset)
    assert cr1
    assert cr1.SOPClassUID
    del cr1.SOPClassUID  # remove required attribute
    test_filename = "test.dcm"
    test_dcm_file_path = Path(temp_dir, test_filename)
    cr1.save_as(test_dcm_file_path)

    error_msg, ds = anonymizer.anonymize_file(test_dcm_file_path)

    assert error_msg
    assert "Missing Attributes" in error_msg
    assert ds == cr1

    # Ensure file is moved to correct quarantine directory:
    qpath = Path(anonymizer.get_quarantine_path(), QuarantineDirectories.MISSING_ATTRIBUTES.value)
    assert qpath.exists()


def test_anonymize_storage_error(temp_dir: str, controller: ProjectController):
    anonymizer: AnonymizerController = controller.anonymizer

    cr1 = get_testdata_file(cr1_filename, read=True)
    assert isinstance(cr1, Dataset)
    assert cr1
    assert cr1.SOPClassUID
    del cr1.file_meta  # remove file_meta

    error_msg = anonymizer.anonymize("Unit Testing", cr1)

    assert error_msg
    assert "Storage Error" in error_msg

    # Ensure file is moved to correct quarantine directory:
    qpath = Path(anonymizer.get_quarantine_path(), QuarantineDirectories.STORAGE_ERROR.value)
    assert qpath.exists()
    filename: Path = anonymizer.local_storage_path(qpath, cr1)
    assert filename.exists()

def test_always_tags_new_private_tag(temp_dir):
    # create custom script and init anonymizer
    script_path = Path(temp_dir) / "custom.script"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(
        """<script>
<e en="T" t="00131010" n="ProjectName">@always()@keep()</e>
<e en="T" t="00080016" n="SOPClassUID">@hashuid</e>
<e en="T" t="00080018" n="SOPInstanceUID">@hashuid</e>
<e en="T" t="0020000D" n="StudyInstanceUID">@hashuid</e>
<e en="T" t="0020000E" n="SeriesInstanceUID">@hashuid</e>
</script>"""
    )
    model = ProjectModel(anonymizer_script_path=script_path, storage_dir=Path(temp_dir, LocalSCU.aet))
    controller = ProjectController(model)

    # remove private tag "ProjectName" if existing
    cr1 : FileDataset= get_testdata_file(cr1_filename, read=True)
    project_name_tag = Tag(0x0013, 0x1010)  
    if project_name_tag in cr1:
        del cr1[project_name_tag]
    with pytest.raises(KeyError):
        assert not cr1[project_name_tag]
    
    # run anonymizer
    test_filename = "test.dcm"
    test_dcm_file_path = Path(temp_dir, test_filename)
    cr1.save_as(test_dcm_file_path)
    error_msg, ds = controller.anonymizer.anonymize_file(test_dcm_file_path)
    controller.anonymizer.stop()

    # test if private tag "ProjectName" exists now
    assert ds[0x00131010] 


def test_always_tags_new_tag(temp_dir):
    # create custom script and init anonymizer
    script_path = Path(temp_dir) / "custom.script"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(
        """<script>
<e en="T" t="00081030" n="StudyDescription">@always()@keep()</e>
<e en="T" t="00080016" n="SOPClassUID">@hashuid</e>
<e en="T" t="00080018" n="SOPInstanceUID">@hashuid</e>
<e en="T" t="0020000D" n="StudyInstanceUID">@hashuid</e>
<e en="T" t="0020000E" n="SeriesInstanceUID">@hashuid</e>
</script>"""
    )
    model = ProjectModel(anonymizer_script_path=script_path, storage_dir=Path(temp_dir, LocalSCU.aet))
    controller = ProjectController(model)

    # remove tag "Study Description" if existing
    cr1 : FileDataset= get_testdata_file(cr1_filename, read=True)
    stud_desc_tag = Tag(0x0008, 0x1030)  
    if stud_desc_tag in cr1:
        del cr1[stud_desc_tag]
    with pytest.raises(KeyError):
        assert not cr1[stud_desc_tag]

    # run anonymizer
    test_filename = "test.dcm"
    test_dcm_file_path = Path(temp_dir, test_filename)
    cr1.save_as(test_dcm_file_path)
    error_msg, ds = controller.anonymizer.anonymize_file(test_dcm_file_path)
    controller.anonymizer.stop()

    # test if tag "Study Description" exists now
    assert ds[0x00081030] # check that study description exists now


def test_always_tag_keep_tag_combination(temp_dir):
    # create custom script and init anonymizer
    script_path = Path(temp_dir) / "custom.script"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(
        """<script>
<e en="T" t="00081030" n="StudyDescription">@always()@keep()</e>
<e en="T" t="00080016" n="SOPClassUID">@hashuid</e>
<e en="T" t="00080018" n="SOPInstanceUID">@hashuid</e>
<e en="T" t="0020000D" n="StudyInstanceUID">@hashuid</e>
<e en="T" t="0020000E" n="SeriesInstanceUID">@hashuid</e>
</script>"""
    )
    model = ProjectModel(anonymizer_script_path=script_path, storage_dir=Path(temp_dir, LocalSCU.aet))
    controller = ProjectController(model)

    # run anonymizer
    cr1 : FileDataset= get_testdata_file(cr1_filename, read=True)
    test_filename = "test.dcm"
    test_dcm_file_path = Path(temp_dir, test_filename)
    cr1.save_as(test_dcm_file_path)
    error_msg, ds = controller.anonymizer.anonymize_file(test_dcm_file_path)
    controller.anonymizer.stop()

    # test if tag "Study Description" exists now
    assert ds[0x00081030].value == "XR C Spine Comp Min 4 Views" # check that study description is the same


def test_always_tag_param_tag_combination(temp_dir):
    # create custom script and init anonymizer
    script_path = Path(temp_dir) / "custom.script"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(
        """<script>
<p t="PROJECTNAME">Project</p>
<e en="T" t="00081030" n="StudyDescription">@always()@param(@projectname)</e>
<e en="T" t="00080016" n="SOPClassUID">@hashuid</e>
<e en="T" t="00080018" n="SOPInstanceUID">@hashuid</e>
<e en="T" t="0020000D" n="StudyInstanceUID">@hashuid</e>
<e en="T" t="0020000E" n="SeriesInstanceUID">@hashuid</e>
</script>"""
    )
    model = ProjectModel(anonymizer_script_path=script_path, storage_dir=Path(temp_dir, LocalSCU.aet))
    controller = ProjectController(model)

    # remove tag "Study Description" if existing
    cr1 : FileDataset= get_testdata_file(cr1_filename, read=True)
    stud_desc_tag = Tag(0x0008, 0x1030)  
    if stud_desc_tag in cr1:
        del cr1[stud_desc_tag]
    with pytest.raises(KeyError):
        assert not cr1[stud_desc_tag]

    # run anonymizer
    test_filename = "test.dcm"
    test_dcm_file_path = Path(temp_dir, test_filename)
    cr1.save_as(test_dcm_file_path)
    error_msg, ds = controller.anonymizer.anonymize_file(test_dcm_file_path)
    controller.anonymizer.stop()

    # test if tag "Study Description" exists now and is changed to param
    assert ds[0x00081030].value == "Project"

def test_param_in_script(temp_dir):
    # create custom script and init anonymizer
    script_path = Path(temp_dir) / "custom.script"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(
        f"""<script>
<p t="PROJECTNAME">Project</p>
<p t="IntegerParam1">123</p>
<p t="My_float_param">23</p>
<e en="T" t="00081030" n="Study Description">@param(@PROJECTNAME)</e>
<e en="T" t="00181404" n="Exposures on Plate">@param(@IntegerParam1)</e>
<e en="T" t="00181041" n="Contrast/Bolus Volume">@param(@My_float_param)</e>
<e en="T" t="00080016" n="SOPClassUID">@hashuid</e>
<e en="T" t="00080018" n="SOPInstanceUID">@hashuid</e>
<e en="T" t="0020000D" n="StudyInstanceUID">@hashuid</e>
<e en="T" t="0020000E" n="SeriesInstanceUID">@hashuid</e>
</script>"""
    )
    model = ProjectModel(anonymizer_script_path=script_path, storage_dir=Path(temp_dir, LocalSCU.aet))
    controller = ProjectController(model)

    # assert files are in dict (they should be all strings here)
    assert controller.anonymizer.model._script_params["projectname"] == "Project"
    assert controller.anonymizer.model._script_params["integerparam1"] == "123"
    assert controller.anonymizer.model._script_params["my_float_param"] == "23"


    # run anonymizer
    cr1 : FileDataset= get_testdata_file(cr1_filename, read=True)
    test_filename = "test.dcm" # AcquisitionDate = 20010101
    test_dcm_file_path = Path(temp_dir, test_filename)
    cr1.save_as(test_dcm_file_path)
    error_msg, ds = controller.anonymizer.anonymize_file(test_dcm_file_path)
    controller.anonymizer.stop()

    # assert field values are replaced by param
    assert ds[0x00081030].value == "Project"
    assert ds[0x00181404].value == int(123)
    assert ds[0x00181041].value == float(23)


def test_pseudo_anon_initialized_at_projectstart(temp_dir: str):
    #import test scans & get orig patient id
    patient_id_tag = Tag(0x0010, 0x0020)

    cr1 = get_testdata_file(cr1_filename, read=True)
    test_dcm_file_path = Path(temp_dir, "test1.dcm")
    orig_id_1 = str(cr1[patient_id_tag].value)
    cr1.save_as(test_dcm_file_path)

    mr_brain = get_testdata_file(mr_brain_filename, read=True)
    test_dcm_file_path_2 = Path(temp_dir, "test2.dcm")
    orig_id_2 = str(mr_brain[patient_id_tag].value)
    mr_brain.save_as(test_dcm_file_path_2)

    # create csv
    pseudo_key_file = Path(temp_dir) / "partial.csv"
    anon_id_1 = "MyNewID-1"
    anon_id_2 = "MyNewID-2"
    with pseudo_key_file.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Original Patient ID", "Anonymized Patient ID"])
        writer.writerow([orig_id_1, anon_id_1])
        writer.writerow([orig_id_2, anon_id_2])

    # run anonymizer
    model = ProjectModel(anonymizer_script_path=Path("src/anonymizer/assets/scripts/default-anonymizer.script"), storage_dir=Path(temp_dir, LocalSCU.aet))
    model.pseudo_key_config.pseudo_key_lookup_enabled = True
    model.pseudo_key_config.pseudo_key_file_path = pseudo_key_file
    controller = ProjectController(model)


    # test if PID is changed
    error_msg, ds1 = controller.anonymizer.anonymize_file(test_dcm_file_path)
    error_msg, ds2 = controller.anonymizer.anonymize_file(test_dcm_file_path_2)
    controller.anonymizer.stop()
    assert ds1[0x00100020].value == anon_id_1
    assert ds2[0x00100020].value == anon_id_2

def test_pseudo_anon_with_default_generation(temp_dir: str):
    #import test scans & get orig patient id
    patient_id_tag = Tag(0x0010, 0x0020)

    cr1 = get_testdata_file(cr1_filename, read=True)
    test_dcm_file_path = Path(temp_dir, "test1.dcm")
    orig_id_1 = str(cr1[patient_id_tag].value)
    cr1.save_as(test_dcm_file_path)

    mr_brain = get_testdata_file(mr_brain_filename, read=True)
    test_dcm_file_path_2 = Path(temp_dir, "test2.dcm")
    orig_id_2 = str(mr_brain[patient_id_tag].value)
    mr_brain.save_as(test_dcm_file_path_2)

    # create csv
    pseudo_key_file = Path(temp_dir) / "partial.csv"
    anon_id_1 = "MyNewID-1"
    with pseudo_key_file.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Original Patient ID", "Anonymized Patient ID"])
        writer.writerow([orig_id_1, anon_id_1])

    # run anonymizer
    model = ProjectModel(anonymizer_script_path=Path("src/anonymizer/assets/scripts/default-anonymizer.script"), storage_dir=Path(temp_dir, LocalSCU.aet))
    model.pseudo_key_config.pseudo_key_lookup_enabled = True
    model.pseudo_key_config.pseudo_key_file_path = pseudo_key_file
    controller = ProjectController(model)


    # test if PID is changed
    error_msg, ds1 = controller.anonymizer.anonymize_file(test_dcm_file_path)
    error_msg, ds2 = controller.anonymizer.anonymize_file(test_dcm_file_path_2)
    controller.anonymizer.stop()
    assert ds1[0x00100020].value == anon_id_1
    assert ds2[0x00100020].value == "MyNewID-000002"

def test_pseudo_anon_name_change(temp_dir: str, caplog):
    #import test scans & get orig patient id
    patient_id_tag = Tag(0x0010, 0x0020)

    cr1 = get_testdata_file(CR_STUDY_3_SERIES_3_IMAGES[0], read=True)
    image1_subject1_file_path = Path(temp_dir, "image1_subject1.dcm")
    orig_id_1 = str(cr1[patient_id_tag].value)
    cr1.save_as(image1_subject1_file_path)

    cr2 = get_testdata_file(CR_STUDY_3_SERIES_3_IMAGES[1], read=True)
    image2_subject1_file_path = Path(temp_dir, "image2_subject1.dcm")
    cr2.save_as(image2_subject1_file_path)

    mr_brain = get_testdata_file(MR_STUDY_3_SERIES_11_IMAGES[0], read=True)
    image1_subject2_file_path = Path(temp_dir, "image1_subject2.dcm")
    orig_id_2 = str(mr_brain[patient_id_tag].value)
    mr_brain.save_as(image1_subject2_file_path)

    mr_brain_2 = get_testdata_file(MR_STUDY_3_SERIES_11_IMAGES[1], read=True)
    image2_subject2_file_path = Path(temp_dir, "image2_subject2.dcm")
    mr_brain_2.save_as(image2_subject2_file_path)

    # create csv files
    pseudo_key_file = Path(temp_dir) / "partial.csv"
    anon_id_1 = "MyNewID-1"
    anon_id_2 = "MyNewID-2"
    with pseudo_key_file.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Original Patient ID", "Anonymized Patient ID"])
        writer.writerow([orig_id_1, anon_id_1])
        writer.writerow([orig_id_2, anon_id_2])
        
    
    pseudo_key_file_2 = Path(temp_dir) / "partial_2.csv"
    anon_id_3 = "MyNewID-3"
    anon_id_4 = "MyNewID-4"
    with pseudo_key_file_2.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Original Patient ID", "Anonymized Patient ID"])
        writer.writerow([orig_id_1, anon_id_3])
        writer.writerow([orig_id_2, anon_id_4])


    # run anonymizer
    model = ProjectModel(anonymizer_script_path=Path("src/anonymizer/assets/scripts/default-anonymizer.script"),storage_dir=Path(temp_dir, LocalSCU.aet))
    model.pseudo_key_config.pseudo_key_lookup_enabled = True
    model.pseudo_key_config.pseudo_key_file_path = pseudo_key_file
    model.pseudo_key_config.quarantine_on_missing_id = False
    controller = ProjectController(model)


    # test if PID is changed (first values)
    error_msg, ds1 = controller.anonymizer.anonymize_file(image1_subject1_file_path)
    error_msg, ds2 = controller.anonymizer.anonymize_file(image1_subject2_file_path)

    assert ds1[0x00100020].value == anon_id_1
    assert ds2[0x00100020].value == anon_id_2

    with caplog.at_level(logging.ERROR):
        model.pseudo_key_config.pseudo_key_file_path = pseudo_key_file_2
        controller.anonymizer.model._post_unpickle()
        error_msg, ds3 = controller.anonymizer.anonymize_file(image2_subject1_file_path)
        error_msg, ds4 = controller.anonymizer.anonymize_file(image2_subject2_file_path)
        controller.anonymizer.stop()
        assert "Two anonymized patient ids found" in [r.message for r in caplog.records if r.levelname == "ERROR"][-1]
        assert ds1[0x00100020].value == anon_id_1 # should remain unchanged
        assert ds2[0x00100020].value == anon_id_2

def test_pseudo_anon_change_of_error_behaviour(temp_dir: str, caplog):
    #import test scans & get orig patient id
    patient_id_tag = Tag(0x0010, 0x0020)

    cr1 = get_testdata_file(CR_STUDY_3_SERIES_3_IMAGES[0], read=True)
    image1_subject1_file_path = Path(temp_dir, "image1_subject1.dcm")
    orig_id_1 = str(cr1[patient_id_tag].value)
    cr1.save_as(image1_subject1_file_path)

    mr_brain = get_testdata_file(MR_STUDY_3_SERIES_11_IMAGES[0], read=True)
    image1_subject2_file_path = Path(temp_dir, "image1_subject2.dcm")
    orig_id_2 = str(mr_brain[patient_id_tag].value)
    mr_brain.save_as(image1_subject2_file_path)


    # create csv files
    pseudo_key_file = Path(temp_dir) / "partial.csv"
    anon_id_1 = "MyNewID-1"
    anon_id_2 = "MyNewID-2"
    with pseudo_key_file.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Original Patient ID", "Anonymized Patient ID"])


    # run anonymizer
    model = ProjectModel(anonymizer_script_path=Path("src/anonymizer/assets/scripts/default-anonymizer.script"),storage_dir=Path(temp_dir, LocalSCU.aet))
    model.pseudo_key_config.pseudo_key_lookup_enabled = True
    model.pseudo_key_config.pseudo_key_file_path = pseudo_key_file
    model.pseudo_key_config.quarantine_on_missing_id = True
    controller = ProjectController(model)


    # test if quarantined (produces error log in caplog)
    error_msg, ds1 = controller.anonymizer.anonymize_file(image1_subject1_file_path)

    # change behaviour
    model.pseudo_key_config.quarantine_on_missing_id = False
    controller.anonymizer.model._post_unpickle()

    # test if not quarantined
    error_msg, ds1 = controller.anonymizer.anonymize_file(image1_subject1_file_path)
    controller.anonymizer.stop()
    assert "No pseudo-anonymized patiend id found" in [r.message for r in caplog.records if r.levelname == "ERROR"][-1]
    assert ds1[0x00100020].value.strip().endswith("000001")

# TODO: Transcoding tests here

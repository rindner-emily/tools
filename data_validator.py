# import io
import json
import csv
# import pandas as pd
import pydicom as dicom
import os
import numpy as np
import argparse
import sys
from tqdm import tqdm
import multiprocessing
import traceback

DEFAULTS = dict(input_req_json_path=None, path_to_dicoms=None, output_dir=None,
                rejected_results_filename="rejected_case_summary.csv",
                accepted_results_filename="accepted_case_summary.csv",
                rejected_results_json="rejected_case_summary.json",
                accepted_results_json="accepted_case_summary.json")
RETURN_CODES = dict(no_error=[0, "no error"], missing_req_input=[1, 'missing required input'],
                    nonexistent_path=[2, 'nonexistent path'], processing_error=[3, 'processing error'])


def analyze_cases(params):
    cases_list = []
    cases_path = params['path_to_dicoms']

    # set() for unique with/i greater for loop
    for dir_name, sub_dirlist, files in os.walk(cases_path):
        for filename in files:
            if ".dcm" in filename.lower():
                cases_list.append(dir_name)
    rejected_cases = {'rejected_cases_list': {}}
    warning_cases = {'warning_cases_list': {}}
    cases_list = sorted(list(set(cases_list)))
    for case_path in tqdm(cases_list):
        files_list = []
        for dir_name, sub_dirlist, files in os.walk(case_path):
            for filename in files:
                if ".dcm" in filename.lower():
                    files_list.append(os.path.join(dir_name, filename))
        # case_label = files_list[0]
        case_label = os.path.split(files_list[0])
        case_label = case_label[0]
        # dcm_meta_slice_list[0] = dicom.read_file(files_list[0])
        dcm_meta_slice_list = []
        for f in range(len(files_list)):
            dcm_meta_slice_list.append(dicom.read_file(files_list[f]))
        with open(params['input_req_json_path']) as d:
            dicom_req = json.load(d)
        print('processing', case_label)
        # acqno_default = {acquisition_number: 1}
        # case terminations (3)
        if not hasattr(dcm_meta_slice_list[0], 'SOPClassUID'):
            # print("SOPClassUID tag does not exist.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('SOPClassUID tag does not exist.')
                continue
        if not hasattr(dcm_meta_slice_list[0], 'AcquisitionNumber'):
            # print('Warning: AcquisitionNumber tag does not exist.')
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append(
                    'Warning: AcquisitionNumber tag does not exist.')
                continue
        if dcm_meta_slice_list[0].SOPClassUID not in dicom_req["DICOMRequirements"]['SOPClassUID']:
            # print('Case does not meet SOPClassUID.')
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append(
                    'Case does not meet SOPClassUID requirements. Input given: '
                    + str(dcm_meta_slice_list[0].SOPClassUID))
                continue
        if hasattr(dcm_meta_slice_list[0], 'AcquisitionNumber'):
            if dcm_meta_slice_list[0].AcquisitionNumber is None or dcm_meta_slice_list[0].AcquisitionNumber == "":
                # print("Warning: AcquisitionNumber missing value.")
                acquisition_number = 1
                if case_label not in rejected_cases['rejected_cases_list']:
                    rejected_cases['rejected_cases_list'][case_label] = []
                    rejected_cases['rejected_cases_list'][case_label].append(
                        'Warning: AcquisitionNumber missing value.')

        # Check that scan is one single series
        series_instance_uid_list = []
        for r in range(len(dcm_meta_slice_list)):
            series_instance_uid_list.append(dcm_meta_slice_list[r].SeriesInstanceUID)
        series_instance_uid_list = list(set(series_instance_uid_list))

        acquisition_number_list = []
        # for r in range(len(dcm_meta_slice_list)):
        #     acquisition_number_list.append(dcm_meta_slice_list[r].AcquisitionNumber)
        for r in range(len(dcm_meta_slice_list)):
            if dcm_meta_slice_list[r].AcquisitionNumber is None or dcm_meta_slice_list[r].AcquisitionNumber == "":
                acquisition_number_list.append(acquisition_number)
            else:
                acquisition_number_list.append(dcm_meta_slice_list[r].AcquisitionNumber)

        # acquisition_number_list = list(set(acquisition_number_list))
        acquisition_number_list = [int(a) for a in acquisition_number_list]

        unique_acq_list = list(set(acquisition_number_list))

        min_acq = min(unique_acq_list)
        dcm_meta_slice_list2 = []
        for a in range(len(acquisition_number_list)):
            if acquisition_number_list[a] == min_acq:
                dcm_meta_slice_list2.append(dcm_meta_slice_list[a])
        dcm_meta_slice_list = dcm_meta_slice_list2

        if len(unique_acq_list) != 1:
            # print("Case has multiple Acquisition Numbers")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append(
                    'Warning: Case has multiple Acquisition Numbers. '
                    + str(len(unique_acq_list))
                    + ' Acquisition Numbers provided.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append(
                    'Warning: Case has multiple Acquisition Numbers. '
                    + str(len(unique_acq_list))
                    + ' Acquisition Numbers provided.')
        if len(series_instance_uid_list) != 1:
            # print("Case has multiple series, single series required.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case has multiple series.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case has multiple series.')
            continue
        if not hasattr(dcm_meta_slice_list[0], 'KVP'):
            # print("Case does not have kVP tag.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have kVP tag.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have kVP tag.')
            continue
        if not hasattr(dcm_meta_slice_list[0], 'Rows'):
            # print("Case does not have Rows tag.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Rows tag.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Rows tag.')
            continue

        if not hasattr(dcm_meta_slice_list[0], 'Columns'):
            # print("Case does not have Columns tag.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Columns tag.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Columns tag.')
            continue
        if not hasattr(dcm_meta_slice_list[0], 'ImagePositionPatient'):
            # print("Case does not have IPP tag.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have IPP tag.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have IPP tag.')
            continue
        if not hasattr(dcm_meta_slice_list[0], 'ImageOrientationPatient'):
            # print("Case does not have IOP tag.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have IOP tag.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have IOP tag.')
            continue
        if not hasattr(dcm_meta_slice_list[0], 'PixelSpacing'):
            # print("Case does not have Pixel Spacing tag.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Pixel Spacing tag.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Pixel Spacing tag.')
            continue
        if not hasattr(dcm_meta_slice_list[0], 'ImageType'):
            # print("Case does not have Image Type tag.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Image Type tag.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Image Type tag.')
            continue
        # warnings
        # if not hasattr(dcm_meta_slice_list[0], 'InstanceNumber'):
        #     if case_label not in warning_cases['warning_cases_list']:
        #         warning_cases['warning_cases_list'][case_label] = []
        #         warning_cases['warning_cases_list'][case_label].append('Case does not have Instance Number tag.')
        #     else:
        #         warning_cases['warning_cases_list'][case_label].append('Case does not have Instance Number tag.')
        #     continue

        # print(x)
        if "LOCALIZER" in dcm_meta_slice_list[0].ImageType:
            # print("Case has incorrect Image Type. Provided Image Type:", dcm_meta_slice_list[0].ImageType,
            #       " LOCALIZER, SCOUT, MIP not accepted.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case has incorrect Image Type: LOCALIZER.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case has incorrect Image Type: LOCALIZER.')
            continue
        if "SCOUT" in dcm_meta_slice_list[0].ImageType:
            # print("Case has incorrect Image Type. Provided Image Type:", dcm_meta_slice_list[0].ImageType,
            #       " LOCALIZER, SCOUT, MIP not accepted.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case has incorrect Image Type: SCOUT.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case has incorrect Image Type: SCOUT.')
            continue
        if "MIP" in dcm_meta_slice_list[0].ImageType:
            # print("Case has incorrect Image Type. Provided Image Type:", dcm_meta_slice_list[0].ImageType,
            #       " LOCALIZER, SCOUT, MIP not accepted.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case has incorrect Image Type: MIP.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case has incorrect Image Type: MIP.')
            continue

        # cerebral cta
        if not hasattr(dcm_meta_slice_list[0], 'PatientPosition'):
            # print("Case does not have PatientPosition tag.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Patient Position tag.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Patient Position tag.')
            continue
        if not hasattr(dcm_meta_slice_list[0], 'Modality'):
            # print("Case does not have Modality tag.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Modality tag.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Modality tag.')
            continue
        if not hasattr(dcm_meta_slice_list[0], 'ConvolutionKernel'):
            # print("Case does not have ConvolutionKernel tag.")
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Convolution Kernel tag.')
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case does not have Convolution Kernel tag.')
            continue

        if "PatientPosition" in dicom_req["DICOMRequirements"]:
            if dcm_meta_slice_list[0].PatientPosition not in dicom_req["DICOMRequirements"]['PatientPosition']:
                # print('Case does not meet Patient Position requirements.')
                if case_label not in rejected_cases['rejected_cases_list']:
                    rejected_cases['rejected_cases_list'][case_label] = []
                    rejected_cases['rejected_cases_list'][case_label].append(
                        'Case does not meet Patient Position requirements. Input given: '
                        + str(dcm_meta_slice_list[0].PatientPosition))
        if "ImageType" in dicom_req["DICOMRequirements"]:
            if dicom_req["DICOMRequirements"]['ImageType'] not in dcm_meta_slice_list[0].ImageType:
                # print('Case does not meet Image Type requirements.')
                if case_label not in rejected_cases['rejected_cases_list']:
                    rejected_cases['rejected_cases_list'][case_label] = []
                    rejected_cases['rejected_cases_list'][case_label].append(
                        'Case does not meet Image Type requirements. Input given: '
                        + str(dcm_meta_slice_list[0].ImageType))
        if "ConvolutionKernel" in dicom_req["DICOMRequirements"]:
            if dicom_req["DICOMRequirements"]['ConvolutionKernel'] not in dcm_meta_slice_list[0].ConvolutionKernel:
                # print('Case does not meet Convolution Kernel requirements.')
                if case_label not in rejected_cases['rejected_cases_list']:
                    rejected_cases['rejected_cases_list'][case_label] = []
                    rejected_cases['rejected_cases_list'][case_label].append(
                        'Case does not meet Convolution Kernel requirements. Input given: '
                        + str(dcm_meta_slice_list[0].ConvolutionKernel))
        if "Modality" in dicom_req["DICOMRequirements"]:
            if dcm_meta_slice_list[0].Modality not in dicom_req["DICOMRequirements"]['Modality']:
                # print('Case does not meet Modality requirements.')
                if case_label not in rejected_cases['rejected_cases_list']:
                    rejected_cases['rejected_cases_list'][case_label] = []
                    rejected_cases['rejected_cases_list'][case_label].append(
                        'Case does not meet Modality requirements. Input given: '
                        + str(dcm_meta_slice_list[0].Modality))
        XFOV = round(dcm_meta_slice_list[0].PixelSpacing[1] * dcm_meta_slice_list[0].Rows, 2)
        YFOV = round(dcm_meta_slice_list[0].PixelSpacing[0] * dcm_meta_slice_list[0].Columns, 2)
        slice_position_list = []
        for r in range(len(dcm_meta_slice_list)):
            slice_position_list.append(float(dcm_meta_slice_list[r].ImagePositionPatient[2]))
        slice_position_list = np.asarray(slice_position_list)
        ZFOV = round(np.amax(slice_position_list) - np.amin(slice_position_list), 2)
        slice_spacing_list = np.abs(np.diff(np.sort(slice_position_list)))
        # list of spacing [1.25 repeated]
        reference_slice_spacing = np.median(slice_spacing_list)
        error_margin = 0.1
        missing_slices = np.where(np.abs(slice_spacing_list - reference_slice_spacing) >
                                  error_margin * reference_slice_spacing)
        # slice_spacing_list = np.round(slice_spacing_list, 2)
        # slice_spacing, counts = np.unique(slice_spacing_list, return_counts=True)
        # slice_spacing_mode = slice_spacing[np.argmax(counts)]
        missing_slices_str = ""
        # missing_slices = np.where(slice_spacing_list != slice_spacing_mode)
        for i in range(len(missing_slices[0])):
            missing_slices_str = missing_slices_str + str(missing_slices[0][i]) + "; "
        # if len(slice_spacing) > 1:
        if len(missing_slices[0]) > 0:
            if case_label not in rejected_cases['rejected_cases_list']:
                rejected_cases['rejected_cases_list'][case_label] = []
                rejected_cases['rejected_cases_list'][case_label].append('Case has missing_slices or dual slices.'
                                                                         + ' Missing slices number: ' +
                                                                         missing_slices_str)
            else:
                rejected_cases['rejected_cases_list'][case_label].append('Case has missing_slices or dual slices.'
                                                                         + ' Missing slices number: ' +
                                                                         missing_slices_str)
        final_slice_spacing = reference_slice_spacing

        # print(len(dcm_meta_slice_list))
        for slice_index in range(len(dcm_meta_slice_list)):
            x = dcm_meta_slice_list[slice_index].InstanceNumber
            try:
                test = int(x)
            except:
                print(case_label, 'warning: missing instance number')

        # slice count will just be the length of the number of slices, you can do this with dcm_meta_slice_list
        slice_count = len(dcm_meta_slice_list)
        # ZFOV = round(slice_count * final_slice_spacing, 2)

        for key in dicom_req["DICOMRequirements"]:
            # SRS 609
            if key.lower() == "MinKVP".lower():
                if dcm_meta_slice_list[0].KVP < dicom_req["DICOMRequirements"][key]:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "KVP too low. Case provided kVP: " + str(
                                round(dcm_meta_slice_list[0].KVP, 2)) + " Minimum kVP allowed: " +
                            str(dicom_req["DICOMRequirements"]['MinKVP']))
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "KVP too low. Case provided kVP: " + str(
                                round(dcm_meta_slice_list[0].KVP, 2)) + "." + " Minimum kVP allowed: " +
                            str(dicom_req["DICOMRequirements"]['MinKVP']))
            if key.lower() == "MaxKVP".lower():
                if dcm_meta_slice_list[0].KVP > dicom_req["DICOMRequirements"][key]:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "KVP too high. Case provided kVP: " + "." + str(round(dcm_meta_slice_list[0].KVP, 2)) +
                            " Maximum kVP allowed: " +
                            str(dicom_req["DICOMRequirements"]['MaxKVP']))
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "KVP too high. Case provided kVP: " + str(round(dcm_meta_slice_list[0].KVP, 2)) + "." +
                            " Maximum kVP allowed: " +
                            str(dicom_req["DICOMRequirements"]['MaxKVP']))
            if key.lower() == "MinSliceThickness".lower():
                if final_slice_spacing < dicom_req["DICOMRequirements"][key]:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Slice Thickness too low. Case provided Slice Thickness: " +
                            str(round(final_slice_spacing, 2)) + "." +
                            " Minimum Slice Thickness allowed: " + str(dicom_req["DICOMRequirements"]
                                                                       ['MinSliceThickness']))
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Slice Thickness too low. Case provided Slice Thickness: " +
                            str(round(final_slice_spacing, 2)) + "." +
                            " Minimum Slice Thickness allowed: " +
                            str(dicom_req["DICOMRequirements"]['MinSliceThickness']) + "mm")
            if key.lower() == "MaxSliceThickness".lower():
                if final_slice_spacing > dicom_req["DICOMRequirements"][key]:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Slice Thickness too large. Case provided Slice Thickness: " +
                            str(round(final_slice_spacing, 2)) + "." +
                            " Maximum Slice Thickness allowed: " +
                            str(dicom_req["DICOMRequirements"]['MaxSliceThickness']) + "mm")
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Slice Thickness too large. Case provided Slice Thickness: " +
                            str(round(final_slice_spacing, 2)) + "." +
                            " Maximum Slice Thickness allowed: " + str(
                                dicom_req["DICOMRequirements"]['MaxSliceThickness']))
            if key.lower() == "MinRows".lower():
                if int(dcm_meta_slice_list[0].Rows) < dicom_req["DICOMRequirements"][key]:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Rows too low. Case provided Rows: " + str(
                                dcm_meta_slice_list[0].Rows) + "." + " Minimum Rows allowed: " +
                            str(dicom_req["DICOMRequirements"]['MinRows']))
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Rows too low. Case provided Rows: " + str(
                                dcm_meta_slice_list[0].Rows) + "." + " Minimum Rows allowed: " +
                            str(dicom_req["DICOMRequirements"]['MinRows']))
            if key.lower() == "MaxRows".lower():
                if int(dcm_meta_slice_list[0].Rows) > dicom_req["DICOMRequirements"][key]:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Rows too large. Case provided Rows: " + str(
                                dcm_meta_slice_list[0].Rows) + "." + " Maximum Rows allowed: " +
                            str(dicom_req["DICOMRequirements"]['MaxRows']))
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Rows too large. Case provided Rows: " + str(
                                dcm_meta_slice_list[0].Rows) + "." + " Maximum Rows allowed: " +
                            str(dicom_req["DICOMRequirements"]['MaxRows']))
            if key.lower() == "MinColumns".lower():
                if int(dcm_meta_slice_list[0].Columns) < dicom_req["DICOMRequirements"][key]:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Columns too low. Case provided Columns: " + str(dcm_meta_slice_list[0].Columns) +
                            " Minimum Columns allowed:" + str(dicom_req["DICOMRequirements"]['MinColumns']))
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Columns too low. Case provided Columns: " + str(dcm_meta_slice_list[0].Columns) + "." +
                            " Minimum Columns allowed: " + str(dicom_req["DICOMRequirements"]['MinColumns']))
            if key.lower() == "MaxColumns".lower():
                if int(dcm_meta_slice_list[0].Columns) > dicom_req["DICOMRequirements"][key]:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Columns too large. Case provided Columns: " + str(dcm_meta_slice_list[0].Columns) + "." +
                            " Maximum Columns allowed: " + str(dicom_req["DICOMRequirements"]['MaxColumns']))
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Columns too large. Case provided Columns: " + str(dcm_meta_slice_list[0].Columns) + "." +
                            " Maximum Columns allowed: " + str(dicom_req["DICOMRequirements"]['MaxColumns']))
            if key.lower() == "MinXFOV".lower():
                if XFOV < dicom_req["DICOMRequirements"]['MinXFOV']:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "XFOV too low. Case provided XFOV: " + str(XFOV) + "." + " Minimum XFOV allowed: " +
                            str(dicom_req["DICOMRequirements"]['MinXFOV']) + "mm")
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "XFOV too low. Case provided XFOV: " + str(XFOV) + "." + " Minimum XFOV allowed: " +
                            str(dicom_req["DICOMRequirements"]['MinXFOV']) + "mm")
            if key.lower() == "MaxXFOV".lower():
                if XFOV > dicom_req["DICOMRequirements"]['MaxXFOV']:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "XFOV too large. Case provided XFOV: " + str(XFOV) + "." + " Maximum XFOV allowed: " +
                            str(dicom_req["DICOMRequirements"]['MaxXFOV']) + "mm")
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "XFOV too large. Case provided XFOV: " + str(XFOV) + "." + " Maximum XFOV allowed: " +
                            str(dicom_req["DICOMRequirements"]['MaxXFOV']) + "mm")
            if key.lower() == "MinYFOV".lower():
                if YFOV < dicom_req["DICOMRequirements"]['MinYFOV']:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "YFOV too low. Case provided YFOV: " + str(YFOV) + "." + " Minimum YFOV allowed: " +
                            str(dicom_req["DICOMRequirements"]['MinYFOV']) + "mm")
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "YFOV too low. Case provided YFOV: " + str(YFOV) + "." + " Minimum YFOV allowed: " +
                            str(dicom_req["DICOMRequirements"]['MinYFOV']) + "mm")
            if key.lower() == "MaxYFOV".lower():
                if YFOV > dicom_req["DICOMRequirements"]['MaxYFOV']:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "YFOV too high. Case provided YFOV: " + str(YFOV) + "." + " Maximum YFOV allowed: " +
                            str(dicom_req["DICOMRequirements"]['MaxYFOV']) + "mm")
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "YFOV too high. Case provided YFOV: " + str(YFOV) + "." + " Maximum YFOV allowed: " +
                            str(dicom_req["DICOMRequirements"]['MaxYFOV']) + "mm")
            if key.lower() == "MinZFOV".lower():
                if ZFOV < dicom_req["DICOMRequirements"]['MinZFOV']:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "ZFOV too low. Case provided ZFOV: " + str(ZFOV) + "." + " Minimum allowed ZFOV: " +
                            str(dicom_req["DICOMRequirements"]['MinZFOV']) + "mm")
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "ZFOV too low. Case provided ZFOV: " + str(ZFOV) + "." + " Minimum allowed ZFOV: " +
                            str(dicom_req["DICOMRequirements"]['MinZFOV']) + "mm")
            if key.lower() == "MaxZFOV".lower():
                if ZFOV > dicom_req["DICOMRequirements"]['MaxZFOV']:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "ZFOV too high. Case provided ZFOV: " + str('ZFOV') + "." + " Maximum allowed ZFOV: " +
                            str(dicom_req["DICOMRequirements"]['MaxZFOV']) + "mm")
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "ZFOV too high. Case provided ZFOV: " + str(ZFOV) + "." + " Maximum allowed ZFOV: " +
                            str(dicom_req["DICOMRequirements"]['MaxZFOV']) + "mm")

            # cerebral cta reqs
            if key.lower() == "MaxPixelSpacing".lower():
                max_pixel_spacing = np.amax(dcm_meta_slice_list[0].PixelSpacing)
                if max_pixel_spacing > dicom_req["DICOMRequirements"][key]:
                    if case_label not in rejected_cases['rejected_cases_list']:
                        rejected_cases['rejected_cases_list'][case_label] = []
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "Pixel Spacing too high. Case provided Pixel Spacing: " + str('MaxPixelSpacing') + "." +
                            " Maximum allowed Pixel Spacing: " +
                            str(dicom_req["DICOMRequirements"]['MaxPixelSpacing']) + "mm")
                    else:
                        rejected_cases['rejected_cases_list'][case_label].append(
                            "PixelSpacing too high. Case provided PixelSpacing: " + str('MaxPixelSpacing') + "." +
                            " Maximum allowed PixelSpacing: " + str(dicom_req["DICOMRequirements"]['MaxPixelSpacing']) +
                            "mm")

    # rejected_cases['number_of_failed_cases'] = (len(rejected_cases['rejected_cases_list'][case_label]))
    # number_failed = rejected_cases['rejected_cases_list']
    rejected_cases['number_of_failed_cases'] = len(rejected_cases['rejected_cases_list'])
    print('Number of failed cases: ', rejected_cases['number_of_failed_cases'])
    # rejected_cases['number_of_failed_cases'] = (len(number_failed.keys()))
    rejected_cases['number_of_total_cases'] = (len(cases_list))
    print('Total number of cases processed: ', rejected_cases['number_of_total_cases'])

    f = open('accepted_cases_summary.csv', 'w')
    for case_label in cases_list:
        if case_label not in rejected_cases['rejected_cases_list']:
            rows = [case_label]
            writer = csv.writer(f, delimiter=',')
            writer.writerow([x.split(',') for x in rows])
    f.close()

    with open(os.path.join(params['output_dir'], params['rejected_results_filename']), "w") as p:
        for key in rejected_cases['rejected_cases_list'].keys():
            p.write("%s, %s\n" % (key, rejected_cases['rejected_cases_list'][key]))
    p.close()


def main() -> int:
    return_code = 0
    parser = argparse.ArgumentParser(description="Rapid Data Validator")
    parser.add_argument('-sr', '--srs_req_json_path', help=
                        "input file path for SRS Requirements JSON file, eg. \'/Users/name/foldername/filename.json\'",
                        type=str, required=False, action="store", dest="input_req_json_path",
                        default=DEFAULTS["input_req_json_path"])
    parser.add_argument('-dc', '--dcm_case_path', help=
                        "input file path for dicom cases, eg. \'/Users/name/foldername\'",
                        type=str, required=False, action="store", dest="path_to_dicoms",
                        default=DEFAULTS["path_to_dicoms"])
    parser.add_argument('-od', '--output_directory', help=
                        "output directory path to export csv results, eg. \'/Users/name/foldername/filename.csv\'",
                        type=str, required=False, action="store", dest="output_dir",
                        default=DEFAULTS["output_dir"])
    parser.add_argument('-rf', '--rejected_results_filename', help=
                        "(optional) name of rejected results file csv, eg. \'/Users/name/foldername/filename.csv\'",
                        type=str, required=False, action="store", dest="rejected_results_filename",
                        default=DEFAULTS["rejected_results_filename"])
    parser.add_argument('-rj', '--rejected_results_json', help=
                        "(optional) name of rejected results file json, eg. \'/Users/name/foldername/filename.json\'",
                        type=str, required=False, action="store", dest="rejected_results_json",
                        default=DEFAULTS["rejected_results_json"])
    parser.add_argument('-af', '--accepted_results_filename', help=
                        "(optional) name of accepted results file csv, eg. \'/Users/name/foldername/filename.csv\'",
                        type=str, required=False, action="store", dest="accepted_results_filename",
                        default=DEFAULTS["accepted_results_filename"])
    parser.add_argument('-aj', '--accepted_results_json', help=
                        "(optional) name of accepted results file json, eg. \'/Users/name/foldername/filename.json\'",
                        type=str, required=False, action="store", dest="accepted_results_json",
                        default=DEFAULTS["accepted_results_json"])
    args = parser.parse_args()
    params = vars(args)
    if params['input_req_json_path'] == DEFAULTS["input_req_json_path"]:
        print(RETURN_CODES['missing_req_input'][1])
        return_code = RETURN_CODES['missing_req_input'][0]
        return return_code
    if params['path_to_dicoms'] == DEFAULTS["path_to_dicoms"]:
        print(RETURN_CODES['missing_req_input'][1])
        return_code = RETURN_CODES['missing_req_input'][0]
        return return_code
    if params['output_dir'] == DEFAULTS["output_dir"]:
        print(RETURN_CODES['missing_req_input'])
        return_code = RETURN_CODES['missing_req_input']
        return return_code
    if not os.path.exists(params['input_req_json_path']):
        print(RETURN_CODES['nonexistent_path'])
        return_code = RETURN_CODES['nonexistent_path']
        return return_code
    if not os.path.exists(params['path_to_dicoms']):
        print(RETURN_CODES['nonexistent_path'])
        return_code = RETURN_CODES['nonexistent_path']
        return return_code
    if not os.path.exists(params['output_dir']):
        print(RETURN_CODES['nonexistent_path'])
        return_code = RETURN_CODES['nonexistent_path']
        return return_code
    try:
        analyze_cases(params)
    except:
        print(RETURN_CODES['processing_error'])
        traceback.print_exc()
        return_code = RETURN_CODES['processing_error']
    return return_code


if __name__ == '__main__':
    multiprocessing.freeze_support()
    return_code = main()
    sys.exit(return_code)

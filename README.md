# OT-2 E. coli Transformation Protocol Builder

This folder contains a Streamlit GUI for generating customized Opentrons OT-2 protocol files from a parameterized transformation protocol template.

## Files

- `app.py` — the user-friendly GUI.
- `Transformation_protocol_template.py` — the OT-2 protocol template.
- `requirements.txt` — Python package requirements.

## How to run

Open a terminal in this folder and run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The GUI will open in your browser. Adjust the settings, check validation, then download the generated `.py` protocol.

## Dilution sliders

The dilution tab has four sliders, one for each well in the 2x2 dilution square:

```text
[ well 1 | well 2 ]
[ well 3 | well 4 ]
```

Each slider sets the target dilution factor, such as 1X, 10X, 20X, or 40X. The app calculates the transfer volume and media volume for each well automatically.

The targets should stay in low-to-high order because the robot performs the dilution serially:

```text
recovered sample -> well 1 -> well 2 -> well 3 -> well 4
```

## Before using on the robot

Always simulate or check the generated protocol in the Opentrons app before running it on the OT-2.


## Presets and dilution grid

The GUI includes preset buttons for current tested OT-2 settings and several NEB-style starting points. Presets only fill editable fields; users can still change every value before exporting.

The visual dilution grid shows the four-well 2x2 square used for each sample in the 384-well dilution plate. It displays target dilution, source dilution, calculated transfer volume, and calculated media volume.

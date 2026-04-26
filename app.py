import ast
import copy
import datetime as dt
import math
import re
from pathlib import Path

import streamlit as st


APP_DIR = Path(__file__).parent
TEMPLATE_PATH = APP_DIR / "Transformation_protocol_template.py"


DEFAULT_CONFIG = {
    "samples": 12,

    "heater_shaker_slot": "10",
    "temperature_module_slot": "1",
    "reservoir_slot": "2",
    "assemblies_slot": "5",
    "p20_tiprack_slot": "4",
    "p300_tiprack_slot": "7",
    "dilution_plate_slot": "8",
    "agar_plate_slots": ["3", "6", "9"],

    "reservoir_labware": "opentrons_tough_4_reservoir_72ml",
    "assemblies_labware": "opentrons_tough_4_reservoir_72ml",
    "recovery_labware": "nest_96_wellplate_200ul_flat",
    "transformation_labware": "nest_96_wellplate_100ul_pcr_full_skirt",
    "dilution_plate_labware": "appliedbiosystemsmicroamp_384_wellplate_40ul",
    "agar_plate_labware": "axygen_96_wellplate_500ul",

    "media_reservoir_index": 0,
    "agar_reservoir_index": 1,

    "dilution_targets": [1, 10, 20, 40],
    "dilution_final_volume": 20.0,
    "minimum_dilution_transfer_vol": 1.0,

    "recovery_media_vol": 90.0,
    "assembly_transfer_vol": 9.0,
    "recovery_transfer_vol": 30.0,
    "mix_volume": 3.0,
    "mix_repetitions": 5,
    "agar_vol": 30.0,
    "plating_vol": 3.0,

    "initial_cold_temp": 4.0,
    "initial_cold_time_min": 30.0,
    "preheat_recovery_temp": 37.0,
    "heat_step_temp": 40.0,
    "heat_step_time_sec": 30.0,
    "post_heat_cold_temp": 4.0,
    "post_heat_cold_time_min": 10.0,
    "recovery_incubation_temp": 75.0,
    "recovery_incubation_time_sec": 300.0,
    "recovery_shake_speed": 300,

    "p20_aspirate_rate": 2.5,
    "p20_dispense_rate": 6.0,
    "p300_aspirate_rate": 40.0,
    "p300_dispense_rate": 70.0,

    "create_agar_plates": False,
    "run_plating": False,
}


PRESETS = {
    "Current tested OT-2": {
        "initial_cold_temp": 4.0,
        "initial_cold_time_min": 30.0,
        "heat_step_temp": 40.0,
        "heat_step_time_sec": 30.0,
        "post_heat_cold_temp": 4.0,
        "post_heat_cold_time_min": 10.0,
        "recovery_incubation_temp": 75.0,
        "recovery_incubation_time_sec": 300.0,
        "recovery_shake_speed": 300,
        "recovery_media_vol": 90.0,
        "notes": "Your tested OT-2 settings. Best for reproducing your validated run.",
    },
    "NEB typical": {
        "initial_cold_temp": 4.0,
        "initial_cold_time_min": 30.0,
        "heat_step_temp": 42.0,
        "heat_step_time_sec": 30.0,
        "post_heat_cold_temp": 4.0,
        "post_heat_cold_time_min": 5.0,
        "recovery_incubation_temp": 37.0,
        "recovery_incubation_time_sec": 3600.0,
        "recovery_shake_speed": 250,
        "recovery_media_vol": 90.0,
        "notes": "Common NEB-style chemical transformation timing.",
    },
    "NEB 10 sec heat shock": {
        "initial_cold_temp": 4.0,
        "initial_cold_time_min": 30.0,
        "heat_step_temp": 42.0,
        "heat_step_time_sec": 10.0,
        "post_heat_cold_temp": 4.0,
        "post_heat_cold_time_min": 5.0,
        "recovery_incubation_temp": 37.0,
        "recovery_incubation_time_sec": 3600.0,
        "recovery_shake_speed": 250,
        "recovery_media_vol": 90.0,
        "notes": "For NEB products/protocols specifying 10 sec at 42°C.",
    },
    "NEB 20 sec heat shock": {
        "initial_cold_temp": 4.0,
        "initial_cold_time_min": 30.0,
        "heat_step_temp": 42.0,
        "heat_step_time_sec": 20.0,
        "post_heat_cold_temp": 4.0,
        "post_heat_cold_time_min": 5.0,
        "recovery_incubation_temp": 37.0,
        "recovery_incubation_time_sec": 3600.0,
        "recovery_shake_speed": 250,
        "recovery_media_vol": 90.0,
        "notes": "For NEB products/protocols specifying 20 sec at 42°C.",
    },
}


def apply_preset(config: dict, preset_name: str) -> dict:
    updated = copy.deepcopy(config)
    for key, value in PRESETS[preset_name].items():
        if key != "notes":
            updated[key] = value
    return updated


def calculate_dilution_plan(config: dict) -> list[dict]:
    final_volume = float(config["dilution_final_volume"])
    source_factor = 1.0
    plan = []

    for target_factor in config["dilution_targets"]:
        target_factor = float(target_factor)
        step_factor = target_factor / source_factor
        transfer_volume = final_volume / step_factor
        media_volume = final_volume - transfer_volume
        plan.append(
            {
                "target_x": target_factor,
                "source_x": source_factor,
                "transfer_ul": transfer_volume,
                "media_ul": media_volume,
                "step_factor": step_factor,
            }
        )
        source_factor = target_factor

    return plan


def validate_config(config: dict) -> list[str]:
    errors = []

    samples = int(config["samples"])
    if not 1 <= samples <= 96:
        errors.append("Samples must be between 1 and 96.")

    sample_cols = math.ceil(samples / 8)
    if sample_cols > 12:
        errors.append("This layout supports up to 12 sample columns.")

    if sample_cols * 2 > 24:
        errors.append("This 384-well dilution layout needs two columns per sample column and supports up to 12 sample columns.")

    positive_keys = [
        "dilution_final_volume",
        "minimum_dilution_transfer_vol",
        "recovery_media_vol",
        "assembly_transfer_vol",
        "recovery_transfer_vol",
        "mix_volume",
        "agar_vol",
        "plating_vol",
    ]
    for key in positive_keys:
        if float(config[key]) <= 0:
            errors.append(f"{key} must be greater than 0.")

    if float(config["assembly_transfer_vol"]) > 20:
        errors.append("Assembly transfer volume must be 20 µL or less because it uses the P20.")

    if float(config["recovery_transfer_vol"]) > 300:
        errors.append("Recovery transfer volume must be 300 µL or less because it uses the P300.")

    targets = [float(x) for x in config["dilution_targets"]]
    if len(targets) != 4:
        errors.append("Exactly four dilution targets are required.")

    previous = 1.0
    for i, target in enumerate(targets, start=1):
        if target < 1:
            errors.append(f"Dilution well {i} must be 1X or higher.")
        if target < previous:
            errors.append("Dilution sliders must stay in low-to-high order.")
        previous = target

    try:
        for i, step in enumerate(calculate_dilution_plan(config), start=1):
            transfer = step["transfer_ul"]
            if transfer < float(config["minimum_dilution_transfer_vol"]):
                errors.append(
                    f"Dilution well {i} needs only {transfer:.2f} µL transfer, below the selected minimum."
                )
            if transfer > 20:
                errors.append(
                    f"Dilution well {i} needs {transfer:.2f} µL transfer, above the P20 max."
                )
            if step["media_ul"] < 0:
                errors.append(f"Dilution well {i} has a negative media volume.")
    except ZeroDivisionError:
        errors.append("Dilution targets cannot include zero.")

    return errors


def replace_config_in_template(template_text: str, config: dict) -> str:
    config_text = "CONFIG = " + repr(config)
    return re.sub(
        r"CONFIG\s*=\s*\{.*?\}\n\n\ndef _validate_config",
        config_text + "\n\n\ndef _validate_config",
        template_text,
        flags=re.DOTALL,
    )


def make_protocol(config: dict) -> str:
    template_text = TEMPLATE_PATH.read_text()
    return replace_config_in_template(template_text, config)


def protocol_filename(config: dict) -> str:
    today = dt.date.today().isoformat()
    samples = int(config["samples"])
    return f"ot2_ecoli_transformation_{samples}_samples_{today}.py"


def load_uploaded_config(uploaded_file):
    raw = uploaded_file.read().decode("utf-8")
    parsed = ast.literal_eval(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Uploaded config must be a Python dictionary.")
    merged = copy.deepcopy(DEFAULT_CONFIG)
    merged.update(parsed)
    return merged


st.set_page_config(
    page_title="OT-2 Transformation Protocol Builder",
    page_icon="🧬",
    layout="wide",
)

st.title("OT-2 E. coli Transformation Protocol Builder")
st.write(
    "Adjust the run settings, check the calculated dilution plan, then download a ready-to-run Opentrons protocol file."
)

st.markdown(
    """
    <style>
    .dilution-card {
        border: 1px solid rgba(128,128,128,0.35);
        border-radius: 14px;
        padding: 16px;
        text-align: center;
        margin-bottom: 10px;
        background: rgba(128,128,128,0.06);
    }
    .dilution-card h3 { margin: 0; font-size: 1.1rem; }
    .dilution-card .big { font-size: 1.8rem; font-weight: 700; margin: 8px 0; }
    .dilution-card .small { font-size: 0.9rem; opacity: 0.8; }
    .warning-card {
        border: 1px solid #e6a100;
        border-radius: 12px;
        padding: 10px 12px;
        background: rgba(230,161,0,0.12);
        margin-top: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "config" not in st.session_state:
    st.session_state.config = copy.deepcopy(DEFAULT_CONFIG)

with st.sidebar:
    st.header("Config tools")
    uploaded = st.file_uploader("Load saved config", type=["txt", "py", "json"])
    if uploaded is not None:
        try:
            st.session_state.config = load_uploaded_config(uploaded)
            st.success("Config loaded.")
        except Exception as exc:
            st.error(f"Could not load config: {exc}")

    if st.button("Reset to defaults"):
        st.session_state.config = copy.deepcopy(DEFAULT_CONFIG)
        st.rerun()

config = copy.deepcopy(st.session_state.config)

tab_run, tab_dilution, tab_deck, tab_advanced, tab_export = st.tabs(
    ["Run setup", "Dilutions", "Deck & labware", "Advanced", "Export"]
)

with tab_run:
    left, right = st.columns(2)

    st.subheader("Protocol presets")
    preset_cols = st.columns(len(PRESETS))
    for idx, preset_name in enumerate(PRESETS):
        with preset_cols[idx]:
            if st.button(preset_name, use_container_width=True):
                config = apply_preset(config, preset_name)
                st.session_state.config = config
                st.rerun()
            st.caption(PRESETS[preset_name]["notes"])

    st.divider()

    with left:
        st.subheader("Samples and workflow")
        config["samples"] = st.number_input(
            "Number of samples",
            min_value=1,
            max_value=96,
            value=int(config["samples"]),
            step=1,
            help="The OT-2 handles samples in 8-channel columns. 12 samples will use 2 columns.",
        )
        st.info(f"Sample columns used: {math.ceil(int(config['samples']) / 8)}")

        config["create_agar_plates"] = st.checkbox(
            "Create agar plates on deck",
            value=bool(config["create_agar_plates"]),
        )
        config["run_plating"] = st.checkbox(
            "Run plating step",
            value=bool(config["run_plating"]),
        )

    with right:
        st.subheader("Core volumes")
        config["assembly_transfer_vol"] = st.number_input("Assembly transfer volume (µL)", 1.0, 20.0, float(config["assembly_transfer_vol"]), 0.5)
        config["recovery_transfer_vol"] = st.number_input("Recovery transfer volume (µL)", 1.0, 300.0, float(config["recovery_transfer_vol"]), 0.5)
        config["recovery_media_vol"] = st.number_input("Recovery media volume (µL)", 1.0, 200.0, float(config["recovery_media_vol"]), 1.0)
        config["agar_vol"] = st.number_input("Agar volume per well (µL)", 1.0, 300.0, float(config["agar_vol"]), 1.0)
        config["plating_vol"] = st.number_input("Plating volume (µL)", 1.0, 20.0, float(config["plating_vol"]), 0.5)

    st.subheader("Temperature and timing")
    a, b, c = st.columns(3)
    with a:
        config["initial_cold_temp"] = st.number_input("Initial cold temp (°C)", 0.0, 25.0, float(config["initial_cold_temp"]), 1.0)
        config["initial_cold_time_min"] = st.number_input("Initial cold time (min)", 0.0, 120.0, float(config["initial_cold_time_min"]), 1.0)
        config["preheat_recovery_temp"] = st.number_input("Heater-Shaker preheat temp (°C)", 20.0, 95.0, float(config["preheat_recovery_temp"]), 1.0)
    with b:
        config["heat_step_temp"] = st.number_input("Heat step temp (°C)", 0.0, 95.0, float(config["heat_step_temp"]), 1.0)
        config["heat_step_time_sec"] = st.number_input("Heat step time (sec)", 0.0, 3600.0, float(config["heat_step_time_sec"]), 5.0)
        config["post_heat_cold_temp"] = st.number_input("Post-heat cold temp (°C)", 0.0, 25.0, float(config["post_heat_cold_temp"]), 1.0)
    with c:
        config["post_heat_cold_time_min"] = st.number_input("Post-heat cold time (min)", 0.0, 120.0, float(config["post_heat_cold_time_min"]), 1.0)
        config["recovery_incubation_temp"] = st.number_input("Recovery incubation temp (°C)", 20.0, 95.0, float(config["recovery_incubation_temp"]), 1.0)
        config["recovery_incubation_time_sec"] = st.number_input("Recovery incubation time (sec)", 0.0, 7200.0, float(config["recovery_incubation_time_sec"]), 30.0)
        config["recovery_shake_speed"] = st.number_input("Recovery shake speed (RPM)", 0, 3000, int(config["recovery_shake_speed"]), 50)

with tab_dilution:
    st.subheader("Four-well dilution square")
    st.write(
        "Each slider sets the target dilution factor for one well in the 2×2 square. "
        "Keep them in low-to-high order."
    )

    config["dilution_final_volume"] = st.number_input(
        "Final volume per dilution well (µL)",
        min_value=1.0,
        max_value=40.0,
        value=float(config["dilution_final_volume"]),
        step=1.0,
    )
    config["minimum_dilution_transfer_vol"] = st.number_input(
        "Minimum allowed transfer volume (µL)",
        min_value=0.5,
        max_value=10.0,
        value=float(config["minimum_dilution_transfer_vol"]),
        step=0.5,
    )

    d1, d2 = st.columns(2)
    d3, d4 = st.columns(2)

    with d1:
        t1 = st.slider("Well 1 target dilution (X)", 1, 200, int(config["dilution_targets"][0]))
    with d2:
        t2 = st.slider("Well 2 target dilution (X)", 1, 500, int(config["dilution_targets"][1]))
    with d3:
        t3 = st.slider("Well 3 target dilution (X)", 1, 1000, int(config["dilution_targets"][2]))
    with d4:
        t4 = st.slider("Well 4 target dilution (X)", 1, 2000, int(config["dilution_targets"][3]))

    config["dilution_targets"] = [t1, t2, t3, t4]
    plan = calculate_dilution_plan(config)

    st.subheader("Visual dilution grid")
    st.write("This mirrors the 2×2 dilution square used for each sample in the 384-well plate.")

    row1_a, row1_b = st.columns(2)
    row2_a, row2_b = st.columns(2)
    grid_cols = [row1_a, row1_b, row2_a, row2_b]

    for i, step in enumerate(plan):
        transfer = step["transfer_ul"]
        media = step["media_ul"]
        warning = ""
        if transfer < float(config["minimum_dilution_transfer_vol"]):
            warning = "Transfer below minimum"
        elif transfer > 20:
            warning = "Transfer above P20 max"

        warning_html = f'<div class="warning-card">⚠ {warning}</div>' if warning else ''
        with grid_cols[i]:
            st.markdown(
                f"""
                <div class="dilution-card">
                    <h3>Well {i + 1}</h3>
                    <div class="big">{step["target_x"]:g}X</div>
                    <div class="small">from {step["source_x"]:g}X source</div>
                    <div class="small">Transfer: <b>{transfer:.2f} µL</b></div>
                    <div class="small">Media: <b>{media:.2f} µL</b></div>
                    {warning_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

    if config["dilution_targets"] != sorted(config["dilution_targets"]):
        st.error("Dilution sliders are out of order. Keep the four wells low-to-high because the protocol performs serial dilution.")
    else:
        st.success("Dilution order is valid.")

    st.subheader("Calculated dilution plan")
    st.dataframe(
        [
            {
                "Dilution well": i + 1,
                "Target dilution": f'{step["target_x"]:g}X',
                "Source dilution": f'{step["source_x"]:g}X',
                "Step factor": f'{step["step_factor"]:g}',
                "Transfer volume (µL)": round(step["transfer_ul"], 2),
                "Media volume (µL)": round(step["media_ul"], 2),
            }
            for i, step in enumerate(plan)
        ],
        use_container_width=True,
        hide_index=True,
    )

with tab_deck:
    st.subheader("Deck slots")
    slots = st.columns(4)
    slot_keys = [
        ("heater_shaker_slot", "Heater-Shaker"),
        ("temperature_module_slot", "Temperature module"),
        ("reservoir_slot", "Media/agar reservoir"),
        ("assemblies_slot", "Assemblies"),
        ("p20_tiprack_slot", "P20 tips"),
        ("p300_tiprack_slot", "P300 tips"),
        ("dilution_plate_slot", "384-well dilution plate"),
    ]

    for idx, (key, label) in enumerate(slot_keys):
        with slots[idx % 4]:
            config[key] = st.text_input(label, str(config[key]))

    agar_slots_text = st.text_input(
        "Agar plate slots, comma-separated",
        ", ".join(config["agar_plate_slots"]),
    )
    config["agar_plate_slots"] = [slot.strip() for slot in agar_slots_text.split(",") if slot.strip()]

    st.subheader("Reservoir channels")
    r1, r2 = st.columns(2)
    with r1:
        config["media_reservoir_index"] = st.number_input("Media reservoir index", 0, 3, int(config["media_reservoir_index"]), 1)
    with r2:
        config["agar_reservoir_index"] = st.number_input("Agar reservoir index", 0, 3, int(config["agar_reservoir_index"]), 1)

    st.subheader("Labware definitions")
    labware_keys = [
        ("reservoir_labware", "Reservoir labware"),
        ("assemblies_labware", "Assemblies labware"),
        ("recovery_labware", "Recovery labware"),
        ("transformation_labware", "Transformation labware"),
        ("dilution_plate_labware", "Dilution plate labware"),
        ("agar_plate_labware", "Agar plate labware"),
    ]
    for key, label in labware_keys:
        config[key] = st.text_input(label, str(config[key]))

with tab_advanced:
    st.subheader("Mixing and flow rates")
    a, b, c = st.columns(3)
    with a:
        config["mix_volume"] = st.number_input("Mix volume (µL)", 1.0, 20.0, float(config["mix_volume"]), 0.5)
        config["mix_repetitions"] = st.number_input("Mix repetitions", 1, 20, int(config["mix_repetitions"]), 1)
    with b:
        config["p20_aspirate_rate"] = st.number_input("P20 aspirate rate", 0.1, 20.0, float(config["p20_aspirate_rate"]), 0.5)
        config["p20_dispense_rate"] = st.number_input("P20 dispense rate", 0.1, 40.0, float(config["p20_dispense_rate"]), 0.5)
    with c:
        config["p300_aspirate_rate"] = st.number_input("P300 aspirate rate", 1.0, 150.0, float(config["p300_aspirate_rate"]), 1.0)
        config["p300_dispense_rate"] = st.number_input("P300 dispense rate", 1.0, 300.0, float(config["p300_dispense_rate"]), 1.0)

with tab_export:
    st.subheader("Validation")
    errors = validate_config(config)

    if errors:
        for error in errors:
            st.error(error)
    else:
        st.success("Configuration looks valid.")

    st.subheader("Run summary")
    st.write(
        f"**{int(config['samples'])} samples** · "
        f"Heat step: **{float(config['heat_step_temp']):g}°C for {float(config['heat_step_time_sec']):g} sec** · "
        f"Recovery/outgrowth: **{float(config['recovery_incubation_temp']):g}°C for {float(config['recovery_incubation_time_sec'])/60:g} min** · "
        f"Dilutions: **{', '.join(str(x) + 'X' for x in config['dilution_targets'])}**"
    )

    st.subheader("Download")
    protocol_text = make_protocol(config)
    filename = protocol_filename(config)

    st.download_button(
        "Download OT-2 protocol (.py)",
        data=protocol_text,
        file_name=filename,
        mime="text/x-python",
        disabled=bool(errors),
    )

    st.download_button(
        "Download config only (.txt)",
        data=repr(config),
        file_name="transformation_config.txt",
        mime="text/plain",
    )

    with st.expander("Preview generated CONFIG"):
        st.code(repr(config), language="python")

    with st.expander("Preview generated protocol"):
        st.code(protocol_text, language="python")

st.session_state.config = config

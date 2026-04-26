from opentrons import protocol_api
import math

metadata = {
    "protocol_name": "E. coli Transformation Efficacy Test - Parameterized",
    "author": "Parker Mace",
    "description": "Parameterized OT-2 protocol template for an E. coli transformation efficacy workflow.",
}

requirements = {
    "robotType": "OT-2",
    "apiLevel": "2.27",
}

# =============================================================================
# USER-EDITABLE PARAMETERS
# A GUI can safely rewrite only this CONFIG dictionary and leave the rest intact.
# =============================================================================
CONFIG = {
    # Run size. This protocol uses multi-channel pipettes, so samples are handled
    # in columns of 8. Example: 12 samples requires 2 columns.
    "samples": 12,

    # Deck slots
    "heater_shaker_slot": "10",
    "temperature_module_slot": "1",
    "reservoir_slot": "2",
    "assemblies_slot": "5",
    "p20_tiprack_slot": "4",
    "p300_tiprack_slot": "7",
    "dilution_plate_slot": "8",
    "agar_plate_slots": ["3", "6", "9"],

    # Labware names
    "reservoir_labware": "opentrons_tough_4_reservoir_72ml",
    "assemblies_labware": "opentrons_tough_4_reservoir_72ml",
    "recovery_labware": "nest_96_wellplate_200ul_flat",
    "transformation_labware": "nest_96_wellplate_100ul_pcr_full_skirt",
    "dilution_plate_labware": "appliedbiosystemsmicroamp_384_wellplate_40ul",
    "agar_plate_labware": "axygen_96_wellplate_500ul",

    # Source reservoir channels
    "media_reservoir_index": 0,
    "agar_reservoir_index": 1,

    # Volumes in microliters. These default values are copied from the tested file.
    # Dilution settings
    # The GUI should expose dilution_targets as four sliders, one for each well
    # in the 2x2 dilution square. Example layout:
    #   [well 1 | well 2]
    #   [well 3 | well 4]
    # Values are dilution factors relative to recovered sample:
    #   1 means undiluted sample, 10 means 1:10, 20 means 1:20, etc.
    #
    # The protocol calculates the required transfer and media volume for each
    # well using serial dilution math. Targets must stay in low-to-high order.
    "dilution_targets": [1, 10, 20, 40],
    "dilution_final_volume": 20,
    "minimum_dilution_transfer_vol": 1,

    "recovery_media_vol": 90,
    "assembly_transfer_vol": 9,
    "recovery_transfer_vol": 30,
    "mix_volume": 3,
    "mix_repetitions": 5,
    "agar_vol": 30,
    "plating_vol": 3,

    # Timings and temperatures. Defaults are copied from the tested file.
    "initial_cold_temp": 4,
    "initial_cold_time_min": 30,
    "preheat_recovery_temp": 37,
    "heat_step_temp": 40,
    "heat_step_time_sec": 30,
    "post_heat_cold_temp": 4,
    "post_heat_cold_time_min": 10,
    "recovery_incubation_temp": 75,
    "recovery_incubation_time_sec": 300,
    "recovery_shake_speed": 300,

    # Pipette flow rates
    "p20_aspirate_rate": 2.5,
    "p20_dispense_rate": 6,
    "p300_aspirate_rate": 40,
    "p300_dispense_rate": 70,

    # Optional workflow steps
    "create_agar_plates": False,
    "run_plating": False,
}


def _validate_config(config: dict) -> None:
    """Catch common user-entry problems before the robot starts moving."""
    samples = int(config["samples"])
    if samples < 1 or samples > 96:
        raise ValueError("samples must be between 1 and 96.")

    required_positive_volumes = [
        "recovery_media_vol",
        "assembly_transfer_vol",
        "recovery_transfer_vol",
        "mix_volume",
        "agar_vol",
        "plating_vol",
    ]
    for key in required_positive_volumes:
        if float(config[key]) <= 0:
            raise ValueError(f"{key} must be greater than 0.")

    if len(config["dilution_targets"]) != 4:
        raise ValueError("dilution_targets must contain exactly 4 dilution factors.")

    previous_target = 1
    final_volume = float(config["dilution_final_volume"])
    min_transfer = float(config["minimum_dilution_transfer_vol"])

    if final_volume <= 0:
        raise ValueError("dilution_final_volume must be greater than 0.")

    for target in config["dilution_targets"]:
        target = float(target)
        if target < 1:
            raise ValueError("Dilution targets must be 1X or greater.")
        if target < previous_target:
            raise ValueError("Dilution targets must stay in low-to-high order.")
        step_factor = target / previous_target
        transfer_vol = final_volume / step_factor
        if transfer_vol < min_transfer:
            raise ValueError(
                "At least one dilution step requires a transfer below "
                "minimum_dilution_transfer_vol. Lower the jump between adjacent "
                "dilution targets, lower the minimum transfer, or increase final volume."
            )
        if transfer_vol > 20:
            raise ValueError(
                "At least one dilution transfer exceeds the P20 max of 20 uL. "
                "Lower dilution_final_volume or use a different transfer strategy."
            )
        previous_target = target

    sample_cols = math.ceil(samples / 8)
    if sample_cols * 2 > 24:
        raise ValueError("Too many sample columns for the current 384-well dilution layout.")

    if sample_cols > 12:
        raise ValueError("Too many sample columns for 96-well plate columns.")


def run(protocol: protocol_api.ProtocolContext):
    config = CONFIG
    _validate_config(config)

    sample_cols = math.ceil(int(config["samples"]) / 8)

    # -------------------------------------------------------------------------
    # Labware and modules
    # -------------------------------------------------------------------------
    hs_mod = protocol.load_module("heaterShakerModuleV1", config["heater_shaker_slot"])
    hs_adapter = hs_mod.load_adapter("opentrons_96_flat_bottom_adapter")
    recover = hs_adapter.load_labware(config["recovery_labware"])

    temp_mod = protocol.load_module("temperature module gen2", config["temperature_module_slot"])
    temp_adapter = temp_mod.load_adapter("opentrons_96_well_aluminum_block")
    transform = temp_adapter.load_labware(config["transformation_labware"])

    reservoir = protocol.load_labware(config["reservoir_labware"], config["reservoir_slot"])
    assemblies = protocol.load_labware(config["assemblies_labware"], config["assemblies_slot"])

    p20_tiprack = protocol.load_labware("opentrons_96_tiprack_20ul", config["p20_tiprack_slot"])
    p20_multi = protocol.load_instrument("p20_multi_gen2", "left", tip_racks=[p20_tiprack])

    p300_tiprack = protocol.load_labware("opentrons_96_tiprack_300ul", config["p300_tiprack_slot"])
    p300_multi = protocol.load_instrument("p300_multi_gen2", "right", tip_racks=[p300_tiprack])

    dil_plate = protocol.load_labware(config["dilution_plate_labware"], config["dilution_plate_slot"])

    agar_plates = tuple(
        protocol.load_labware(config["agar_plate_labware"], slot)
        for slot in config["agar_plate_slots"]
    )

    # -------------------------------------------------------------------------
    # Pipette behavior
    # -------------------------------------------------------------------------
    p20_multi.flow_rate.aspirate = config["p20_aspirate_rate"]
    p20_multi.flow_rate.dispense = config["p20_dispense_rate"]
    p300_multi.flow_rate.aspirate = config["p300_aspirate_rate"]
    p300_multi.flow_rate.dispense = config["p300_dispense_rate"]

    # Multi-channel pipettes address one representative well per column.
    assembly_wells = assemblies.rows()[0][:sample_cols]
    recovery_wells = recover.rows()[0][:sample_cols]
    trans_wells = transform.rows()[0][:sample_cols]

    dilution_wells = {}
    for i in range(sample_cols):
        col_start = 2 * i
        dilution_wells[i] = (
            dil_plate.rows()[0][col_start],
            dil_plate.rows()[0][col_start + 1],
            dil_plate.rows()[1][col_start],
            dil_plate.rows()[1][col_start + 1],
        )

    agar_height = (config["agar_vol"] * 0.001) / (math.pi * math.sqrt(3.43))

    def calculate_dilution_plan():
        """
        Convert four GUI-selected dilution factors into serial dilution steps.

        For each dilution well:
        - source_factor is the dilution factor of the source liquid.
        - target_factor is the desired final dilution in this well.
        - step_factor = target_factor / source_factor.
        - transfer_volume = final_volume / step_factor.
        - media_volume = final_volume - transfer_volume.
        """
        final_volume = float(config["dilution_final_volume"])
        plan = []
        source_factor = 1.0

        for target_factor in config["dilution_targets"]:
            target_factor = float(target_factor)
            step_factor = target_factor / source_factor
            transfer_volume = final_volume / step_factor
            media_volume = final_volume - transfer_volume

            plan.append({
                "target_factor": target_factor,
                "transfer_volume": transfer_volume,
                "media_volume": media_volume,
            })
            source_factor = target_factor

        return plan

    dilution_plan = calculate_dilution_plan()

    def create_plates(plate_vol: float) -> None:
        """Create 96-well agar plates using agar from the configured reservoir channel."""
        agar_source = reservoir.wells()[config["agar_reservoir_index"]]
        p300_multi.pick_up_tip()
        for i in range(sample_cols):
            for plate in agar_plates:
                dest = plate.columns()[i][0]
                p300_multi.aspirate(volume=plate_vol, location=agar_source)
                p300_multi.dispense(volume=plate_vol, location=dest)
                p300_multi.blow_out(dest.top())
        p300_multi.return_tip()

    def distribute_media(recovery_vol: float) -> None:
        """Distribute calculated media volumes to dilution wells and recovery wells."""
        media_source = reservoir.wells()[config["media_reservoir_index"]]
        p300_multi.pick_up_tip()

        for i in range(sample_cols):
            for dilution_index, well in enumerate(dilution_wells[i]):
                media_vol = dilution_plan[dilution_index]["media_volume"]
                if media_vol > 0:
                    p300_multi.aspirate(volume=media_vol, location=media_source)
                    p300_multi.dispense(volume=media_vol, location=well)
                    p300_multi.blow_out(well.top())

        for well in recovery_wells:
            p300_multi.aspirate(volume=recovery_vol, location=media_source)
            p300_multi.dispense(volume=recovery_vol, location=well)
            p300_multi.blow_out(well.top())

        p300_multi.return_tip()

    def transformation(assembly_vol: float) -> None:
        """Transfer assemblies into the transformation plate."""
        for source in assembly_wells:
            dest = transform.well(source.well_name)
            p20_multi.pick_up_tip()
            p20_multi.aspirate(volume=assembly_vol, location=source)
            p20_multi.dispense(volume=assembly_vol, location=dest)
            p20_multi.blow_out(dest.top())
            p20_multi.return_tip()

    def recovery(recover_vol: float) -> None:
        """Transfer transformed samples into recovery wells."""
        for source in trans_wells:
            dest = recover.well(source.well_name)
            p20_multi.pick_up_tip()
            p20_multi.aspirate(volume=recover_vol, location=source)
            p20_multi.dispense(volume=recover_vol, location=dest)
            p20_multi.blow_out(dest.top())
            p20_multi.return_tip()

    def dilutions() -> None:
        """Serial dilution of transformed samples using GUI-selected target factors."""
        for i in range(sample_cols):
            sources = [
                recover.columns()[i][0],
                dilution_wells[i][0],
                dilution_wells[i][1],
                dilution_wells[i][2],
            ]

            p20_multi.pick_up_tip()
            for dilution_index, dest in enumerate(dilution_wells[i]):
                transfer_vol = dilution_plan[dilution_index]["transfer_volume"]
                source = sources[dilution_index]
                p20_multi.aspirate(volume=transfer_vol, location=source)
                p20_multi.dispense(volume=transfer_vol, location=dest)
                p20_multi.mix(repetitions=config["mix_repetitions"], volume=config["mix_volume"])
            p20_multi.return_tip()

    def plating() -> None:
        """Plate selected dilution points onto agar plates."""
        p20_multi.well_bottom_clearance.dispense = agar_height + 0.3
        for i in range(sample_cols):
            p20_multi.pick_up_tip()
            p20_multi.aspirate(volume=config["plating_vol"], location=dilution_wells[i][3])
            p20_multi.dispense(volume=config["plating_vol"], location=agar_plates[0].wells()[i])
            p20_multi.aspirate(volume=config["plating_vol"], location=dilution_wells[i][2])
            p20_multi.dispense(volume=config["plating_vol"], location=agar_plates[1].wells()[i])
            p20_multi.aspirate(volume=config["plating_vol"], location=dilution_wells[i][1])
            p20_multi.dispense(volume=config["plating_vol"], location=agar_plates[2].wells()[i])
            p20_multi.return_tip()

    # -------------------------------------------------------------------------
    # Main workflow
    # -------------------------------------------------------------------------
    temp_mod.set_temperature(celsius=config["initial_cold_temp"])
    protocol.delay(minutes=config["initial_cold_time_min"])

    hs_mod.start_set_temperature(celsius=config["preheat_recovery_temp"])

    if config["create_agar_plates"]:
        create_plates(config["agar_vol"])

    distribute_media(config["recovery_media_vol"])
    transformation(config["assembly_transfer_vol"])

    temp_mod.set_temperature(celsius=config["heat_step_temp"])
    protocol.delay(seconds=config["heat_step_time_sec"])
    temp_mod.set_temperature(celsius=config["post_heat_cold_temp"])
    protocol.delay(minutes=config["post_heat_cold_time_min"])
    temp_mod.deactivate()

    recovery(config["recovery_transfer_vol"])

    heat_task = hs_mod.start_set_temperature(celsius=config["recovery_incubation_temp"])
    hs_mod.set_shake_speed(rpm=config["recovery_shake_speed"])
    protocol.wait_for_tasks([heat_task])
    protocol.delay(seconds=config["recovery_incubation_time_sec"])
    hs_mod.deactivate_heater()
    hs_mod.deactivate_shaker()

    dilutions()

    if config["run_plating"]:
        plating()

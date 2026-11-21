"""AQ6315A/B GP-IB program-code table (manual chapter 9, Table 9-2, pages 9-5 .. 9-35).

Every entry is data; ando_osa.osa.Osa turns each one into Python methods:

    kind "action"   -> osa.<name>()                      sends  CODE
    kind "number"   -> osa.set_<name>(x) / get_<name>()  sends  CODE<x>   /  QUERY
    kind "choice"   -> osa.set_<name>(x) / get_<name>()  x is a key of `enum`
    kind "query"    -> osa.get_<name>()                  sends  QUERY

`page` is the manual page (e.g. "9-6"). Entries flagged unverified=True were
hard to read in the scan or have ambiguous syntax; confirm on the instrument.

Floppy-disk (FD) commands (WR*, RD*, DEL, DSKIN, ...) and printer/plotter
commands are intentionally NOT included yet: the Pi has no floppy, and they
can be added later with the same helpers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Cmd:
    name: str                       # python-friendly name
    code: str                       # control-command stem as sent over GPIB
    kind: str                       # action | number | choice | query
    group: str = ""
    doc: str = ""
    page: str = ""
    query: Optional[str] = None     # talker command (e.g. "CTRWL?")
    lo: Optional[float] = None
    hi: Optional[float] = None
    decimals: int = 0               # digits after the point when sending numbers
    special: tuple = ()             # extra legal numeric values outside lo..hi (e.g. span 0)
    enum: dict = field(default_factory=dict)   # python key -> value sent / returned
    reply: str = "float"            # float | int | str | enum
    unit: str = ""
    unverified: bool = False


_TABLE: list[Cmd] = []


def _add(c: Cmd) -> Cmd:
    _TABLE.append(c)
    return c


def action(name, code, group, doc, page, **kw):
    return _add(Cmd(name, code, "action", group, doc, page, **kw))


def number(name, code, group, doc, page, lo, hi, decimals=0, unit="", query=True, reply="float", **kw):
    q = code + "?" if query is True else (query or None)
    return _add(Cmd(name, code, "number", group, doc, page, query=q, lo=lo, hi=hi,
                    decimals=decimals, unit=unit, reply=reply, **kw))


def choice(name, code, group, doc, page, enum, query=True, reply="enum", **kw):
    q = code + "?" if query is True else (query or None)
    return _add(Cmd(name, code, "choice", group, doc, page, query=q, enum=enum, reply=reply, **kw))


def onoff(name, code, group, doc, page, **kw):
    return choice(name, code, group, doc, page, {"off": 0, "on": 1}, **kw)


def query(name, qcode, group, doc, page, reply="str", **kw):
    return _add(Cmd(name, qcode.rstrip("?"), "query", group, doc, page, query=qcode, reply=reply, **kw))


# ---------------------------------------------------------------- SWEEP (9-5)
G = "sweep"
action("auto_sweep", "AUTO", G, "Start an auto sweep.", "9-5")
action("repeat_sweep", "RPT", G, "Start a repeat sweep.", "9-5")
action("single_sweep", "SGL", G, "Start a single sweep.", "9-5")
action("segment_measure", "SMEAS", G, "Measure according to the set sampling count (segment measure).", "9-5")
action("stop_sweep", "STP", G, "Stop a sweep.", "9-5")
query("sweep_status", "SWEEP?", G, "Measurement status: 0 STOP,1 SINGLE,2 REPEAT,3 AUTO,4 SEGMENT MEASURE.", "9-5", reply="int")
number("seg_points", "SEGP", G, "Sampling count for SEGMENT MEASURE.", "9-5", 1, 1001, reply="int")
onoff("sweep_mkr_l1_l2", "SWPM", G, "Marker-to-marker sweep (L1-L2) on/off.", "9-5", reply="int")
number("sweep_interval", "SWPI", G, "Time from sweep start to next sweep start in repeat mode (s); 0 = minimum.", "9-5", 0, 99999, unit="s", reply="int")

# ---------------------------------------------------------------- CENTER (9-6)
G = "center"
number("center_wl", "CTRWL", G, "Center wavelength.", "9-6", 350.0, 1750.0, 2, "nm")
number("start_wl", "STAWL", G, "Measurement start wavelength.", "9-6", -400.0, 1750.0, 2, "nm")
number("stop_wl", "STPWL", G, "Measurement stop wavelength.", "9-6", 350.0, 2500.0, 2, "nm")
action("peak_to_center", "CTR=P", G, "Set waveform peak wavelength as center wavelength.", "9-6")
onoff("auto_center", "ATCTR", G, "Peak->center at each sweep on/off.", "9-6", reply="int")

# ---------------------------------------------------------------- SPAN (9-6)
G = "span"
number("span", "SPAN", G, "Span (0 allowed = zero-span).", "9-6", 1.0, 1500.0, 1, "nm", special=(0,))
action("marker_span", "SPN=W", G, "Set span from the delta-lambda (L1-L2) marker range.", "9-6", query=None)
number("zero_span_sweep_time", "ZSWPT", G, "Sweep time at 0 nm span; 0 = minimum.", "9-6", 0, 50, unit="s", reply="int")

# ---------------------------------------------------------------- LEVEL (9-7, 9-8)
G = "level"
number("ref_level", "REFL", G, "Reference level in LOG mode.", "9-7", -90.0, 20.0, 1, "dBm",
       query="REFL?")
# linear-mode reference level setters (pW/nW/uW/mW); read back through REFL?
number("ref_level_pw", "REFLP", G, "Ref level, linear (pW). 1.00-9.99 step .01, 10.0-99.9 step .1, 100-999 step 1.", "9-7", 1.0, 999.0, 2, "pW", query=False)
number("ref_level_nw", "REFLN", G, "Ref level, linear (nW).", "9-7", 1.0, 999.0, 2, "nW", query=False)
number("ref_level_uw", "REFLU", G, "Ref level, linear (uW).", "9-7", 1.0, 999.0, 2, "uW", query=False)
number("ref_level_mw", "REFLM", G, "Ref level, linear (mW); 10.0-100 step 0.1.", "9-7", 1.0, 100.0, 2, "mW", query=False)
query("ref_level_any", "REFL?", G, "Ref level as returned in current scale: dBm number, or 'PW|NW|UW|MW <value>'.", "9-7")
number("level_scale", "LSCL", G, "Level axis scale (dB/DIV); in LIN scale query returns 0.", "9-7", 0.1, 10.0, 1, "dB/div")
number("base_level", "BASL", G, "Bottom scale value in linear scale mode (= REF LEVEL x 0.9 max).", "9-7", 0.0, 999.0, 1, "mW", query="BASL?")
action("peak_to_ref", "REF=P", G, "Set peak level as reference level.", "9-7")
onoff("auto_ref_level", "ATREF", G, "Peak->ref level at each sweep on/off.", "9-7", reply="int")
choice("level_unit", "LSUNT", G, "Level axis unit: dBm(W) or dBm/nm (W/nm).", "9-8", {"dBm": 0, "dBm/nm": 1}, reply="int")
number("sublog", "SLOG", G, "Subscale (LOG), dB/div.", "9-8", 0.1, 10.0, 1)
number("sublin", "SLIN", G, "Subscale (LINEAR), step 0.005.", "9-8", 0.005, 1.250, 3)
number("sub_scale_db_km", "SKM", G, "Subscale in dB/km.", "9-8", 0.1, 10.0, 1)
number("sub_scale_pct", "SPS", G, "Subscale in %/D.", "9-8", 0.5, 125.0, 1)
number("level_offset", "LOFST", G, "Offset level of the scale (dB).", "9-8", -99.9, 99.9, 1, "dB")
number("level_offset_km", "LOFSKM", G, "Offset of subscale (dB/km).", "9-8", -99.9, 99.9, 1, "dB/km")
number("scale_min_lin", "SMIN", G, "Bottom scale in Linear subscale mode (x10 /DIV).", "9-8", 0.0, 12.5, 1)
number("scale_min_pct", "SMINP", G, "Bottom scale in % subscale mode (x10 /DIV).", "9-8", 0.0, 1250.0, 1)
number("fiber_length", "LNGT", G, "Optical fiber length.", "9-8", 0.001, 99.999, 3, "km")
onoff("auto_subscale", "ATSCL", G, "Auto scaling display on/off.", "9-8", reply="int")

# ---------------------------------------------------------------- SETUP (9-9, 9-10)
G = "setup"
number("resolution", "RESLN", G, "Resolution (1-2-5 steps: 0.05 ... 10.0).", "9-9", 0.05, 10.0, 2, "nm")
choice("sensitivity", "SENS", G, "Measuring sensitivity. Set codes: SNHD, SNAT, SHI1, SHI2, SHI3; SENS? returns 1..5.", "9-9",
       {"norm_hold": 4, "norm_auto": 5, "high1": 1, "high2": 2, "high3": 3}, query="SENS?", reply="enum",
       )
number("averaging", "AVG", G, "Number of averages.", "9-9", 1, 1000, reply="int")
number("sampling_points", "SMPL", G, "Sampling points.", "9-9", 11, 1001, reply="int")
choice("light_mode", "CWPLS", G, "CW (CLMES) or PULSE (PLMES) light measurement; CWPLS? returns 0 pulse / 1 CW.", "9-10",
       {"pulse": 0, "cw": 1}, query="CWPLS?", reply="int")
query("chop_light_mode", "PLMOD?", G, "Chop-light mode: 0 LPF, 1 EXT TRG, 2+hold time = PEAK HOLD.", "9-10", reply="int")
action("lpf_mode", "LPF", G, "Chop-light measurement via lowpass filter.", "9-10")
number("peak_hold_ms", "PKHLD", G, "Chop-light measurement via peak hold; hold time ms.", "9-10", 1, 9999, unit="ms", query=False, reply="int")
action("ext_trigger_mode", "EXTRG", G, "Chop-light measurement via external trigger.", "9-10")
choice("monochromator", "MONO", G, "Single or double monochromator.", "9-10", {"single": 0, "double": 1}, reply="int")
choice("chop_source", "CHOP", G, "Chopping: internal or external.", "9-10", {"internal": 0, "external": 1}, reply="int")

# ---------------------------------------------------------------- MARKER (9-11, 9-12)
G = "marker"
number("marker_wl", "WMKR", G, "Moving marker to wavelength.", "9-11", -400.0, 2500.0, 3, "nm", query=False)
number("marker_thz", "FMKR", G, "Moving marker to frequency.", "9-11", 110.0, 9999.9990, 4, "THz", query=False)
query("marker", "MKR?", G, "Wavelength/frequency and level at moving marker (Table 9-4, 9-39).", "9-11")
action("marker_to_center", "CTR=M", G, "Moving marker wavelength -> center wavelength.", "9-11")
action("marker_to_ref", "REF=M", G, "Moving marker level -> reference level.", "9-11")
action("set_marker1", "MKR1", G, "Set moving marker to fixed marker 1.", "9-11")
action("set_marker2", "MKR2", G, "Set moving marker to fixed marker 2.", "9-11")
query("marker1", "MKR1?", G, "Wavelength and level at fixed marker 1.", "9-11")
query("marker2", "MKR2?", G, "Wavelength and level at fixed marker 2.", "9-11")
action("marker_clear", "MKCL", G, "Clear moving marker, fixed markers and marker values.", "9-11")
choice("marker_unit", "MKUNT", G, "Marker value unit nm or THz.", "9-11", {"nm": 0, "THz": 1}, reply="int")
number("line_marker1_nm", "L1MK", G, "Wavelength line marker 1.", "9-11", -400.0, 2500.0, 3, "nm", query="L1MK?", reply="str")
number("line_marker1_thz", "L1FMK", G, "Wavelength line marker 1 (frequency).", "9-11", 110.0, 9999.9990, 4, "THz", query=False)
number("line_marker2_nm", "L2MK", G, "Wavelength line marker 2.", "9-11", -400.0, 2500.0, 3, "nm", query="L2MK?", reply="str")
number("line_marker2_thz", "L2FMK", G, "Wavelength line marker 2 (frequency).", "9-11", 110.0, 9999.9990, 4, "THz", query=False)
number("line_marker3_dbm", "L3DBM", G, "Level line marker 3 (LOG).", "9-12", -150.0, 40.0, 2, "dBm", query="L3MK?", reply="str")
number("line_marker3_db", "L3DB", G, "Level line marker 3 (SUBLOG).", "9-12", -139.9, 139.9, 2, "dB", query=False)
number("line_marker4_dbm", "L4DBM", G, "Level line marker 4 (LOG).", "9-12", -150.0, 40.0, 2, "dBm", query="L4MK?", reply="str")
number("line_marker4_db", "L4DB", G, "Level line marker 4 (SUBLOG).", "9-12", -139.9, 139.9, 2, "dB", query=False)
action("marker_l1l2_to_span", "SP=LM", G, "Set the L1-L2 section as sweep range.", "9-12")
onoff("search_l1_l2", "SRLMK", G, "Peak detection restricted to L1-L2 on/off.", "9-12", reply="int")
action("line_marker_clear", "LMKCL", G, "Clear line markers and line marker values.", "9-12")
# L3LN / L4LN take scientific notation (0 to 1.360E+02) -> use send("L3LN1.000E-03")

# ---------------------------------------------------------------- PEAK SEARCH (9-12)
G = "search"
action("peak_search", "PKSR", G, "Detect MAX value of level.", "9-12")
action("bottom_search", "BTSR", G, "Detect MIN value of level.", "9-12")
action("next_search", "NSR", G, "Next largest (or next smallest) value.", "9-12")
action("next_search_right", "NSRR", G, "Largest (smallest) value to the right of moving marker.", "9-12")
# v0.1 had "MSRL" (scan read); pairs with NSRR, so almost certainly "NSRL". Confirm on hardware.
action("next_search_left", "NSRL", G, "Largest (smallest) value to the left of moving marker.", "9-12", unverified=True)
query("search_mode", "PKSR?", G, "0 = BOTTOM, 1 = PEAK (last search type).", "9-12", reply="int")
onoff("auto_search", "ATSR", G, "Automatic peak/bottom detection after sweep on/off.", "9-12", reply="int")
number("mode_diff_search", "MODIF", G, "Level difference for mode judgment (dB).", "9-12", 0.0, 50.0, 2, "dB")

# ---------------------------------------------------------------- ANALYSIS (9-13 .. 9-17)
G = "analysis"
choice("spec_width_method", "SW", G, "Spectrum width method: ENVELOPE 0, THRESH 1, RMS 2, PEAK RMS 3, NOTCH 4.", "9-13",
       {"envelope": 0, "thresh": 1, "rms": 2, "peak_rms": 3, "notch": 4}, reply="int")
action("spec_width_envelope", "SWENV", G, "Measure spectrum width, Envelope method.", "9-13")
number("env_th1", "ENVT1", G, "Envelope: threshold (dB).", "9-13", 0.1, 10.0, 1, "dB")
number("env_th2", "ENVT2", G, "Envelope: truncation limit (dB).", "9-13", 0.1, 30.0, 1, "dB")
number("env_k", "ENVK", G, "Envelope: magnification ratio K.", "9-13", 1.0, 10.0, 2)
action("spec_width_thresh", "SWTHR", G, "Measure spectrum width, Threshold method.", "9-13")
number("thresh_th", "THRTH", G, "Threshold method: threshold (dB).", "9-13", 0.1, 50.0, 1, "dB")
number("thresh_k", "THRK", G, "Threshold method: magnification ratio K.", "9-13", 1.0, 10.0, 2)
choice("mode_fit", "MODFT", G, "Mode-fit marker: 1 = mode peak, 0 = threshold level position.", "9-13",
       {"threshold_level": 0, "mode_peak": 1}, reply="int")
action("spec_width_rms", "SWRMS", G, "Measure spectrum width, RMS method.", "9-14")
number("rms_th", "RMSTH", G, "RMS: truncation limit (dB).", "9-14", 0.1, 30.0, 1, "dB")
number("rms_k", "RMSK", G, "RMS: magnification ratio K.", "9-14", 1.0, 10.0, 2)
action("spec_width_peak_rms", "SWPRM", G, "Measure spectrum width, Peak RMS method.", "9-14")
number("peak_rms_th", "PRMTH", G, "Peak RMS: truncation limit (dB).", "9-14", 0.1, 30.0, 1, "dB")
number("peak_rms_k", "PRMK", G, "Peak RMS: magnification ratio K.", "9-14", 1.0, 10.0, 2)
action("spec_width_notch", "SWNCH", G, "Measure the notch width.", "9-14")
number("notch_th", "NCHTH", G, "Notch width threshold (dB).", "9-14", 0.1, 50.0, 1, "dB")
choice("smsr_ref", "SMSR", G, "Reference to measure side-mode suppress ratio (1 or 2). Send 'SMSR1'/'SMSR2'.", "9-14",
       {"1": 1, "2": 2}, reply="int")
number("smsr_mask", "SSMSK", G, "SMSR1 mask range around peak (nm).", "9-14", 0.0, 99.99, 2, "nm")
action("analyze_power", "PWR", G, "Measure marker-to-marker power.", "9-15")
number("power_offset", "POFS", G, "Compensation for marker-to-marker power (dB).", "9-15", -10.0, 10.0, 2, "dB")
action("analyze_fp_ld", "FPAN", G, "Analyze Fabry-Perot laser diode.", "9-15")
action("analyze_dfb_ld", "DFBAN", G, "Analyze DFB laser diode.", "9-15")
action("analyze_led", "LEDAN", G, "Analyze light emitting diode.", "9-15")
action("analyze_color", "COLAN", G, "Analyze the colors.", "9-15")
action("analyze_edfa_nf", "EDNF", G, "Calculate EDFA noise figure.", "9-15")
number("nf_offset_in", "OFIN", G, "Offset of signal light (dB).", "9-15", -99.99, 99.99, 2, "dB")
number("nf_offset_out", "OFOUT", G, "Offset of output light (dB).", "9-15", -99.99, 99.99, 2, "dB")
number("nf_plus_mask", "PLMSK", G, "Mask range right to peak (nm).", "9-15", 0.0, 10.0, 2, "nm")
number("nf_minus_mask", "MIMSK", G, "Mask range left to peak (nm).", "9-15", 0.0, 10.0, 2, "nm")
choice("nf_curve_fit", "EDFCVF", G, "NF curve fit type.", "9-16",
       {"gaussian": 0, "lorenzian": 1, "poly3": 2, "poly4": 3, "poly5": 4}, reply="int")
number("nf_fit_threshold", "EDFTH", G, "Curve fitting threshold (dB).", "9-16", 0.1, 99.9, 1, "dB")
action("analyze_wdm", "WDMAN", G, "Analyze the WDM.", "9-16")
choice("wdm_display", "WDMOS", G, "WDM list display: OFFSET 0 / SPACING 1.", "9-16", {"offset": 0, "spacing": 1}, reply="int")
action("wdm_ref_highest", "WDMRH", G, "Reference = highest channel peak.", "9-16")
number("wdm_ref_wl", "WDMRW", G, "Reference = channel peak closest to wavelength.", "9-16", 350.0, 1750.0, 2, "nm")
number("wdm_ref_channel", "WDMRN", G, "Reference = n-th channel peak.", "9-16", 1, 99, reply="int")
number("wdm_threshold", "WDMTH", G, "Channel-peak threshold (dB).", "9-16", 0.1, 50.0, 1, "dB")
number("wdm_max_channels", "WDMMAX", G, "Maximum number of channel peaks.", "9-16", 1, 99, reply="int")
number("wdm_mode_diff", "WDMDIF", G, "Min. top-to-bottom difference for channel peak detection (dB).", "9-16", 0.0, 50.0, 1, "dB", unverified=True)
onoff("auto_analysis", "ATANA", G, "Auto-execute selected analysis after sweep.", "9-17", reply="int")
query("analysis", "ANA?", G, "Analysis result (format depends on analysis type; Table 9-4, 9-40..9-44).", "9-34")

# ---------------------------------------------------------------- TRACE (9-19 .. 9-21)
G = "trace"
query("trace_a_mode", "TRA?", G, "Trace A mode: 0 WRITE, 1 FIX, 2 MAX HLD, 3+n ROLL AVG.", "9-19", reply="int")
action("write_a", "WRTA", G, "Trace A write mode.", "9-19")
action("fix_a", "FIXA", G, "Trace A fixed.", "9-19")
action("max_hold_a", "MAXA", G, "Trace A max-hold.", "9-19")
number("roll_avg_a", "RAVA", G, "Trace A sequential (rolling) averaging, 2..100.", "9-19", 2, 100, reply="int", query=False)
action("display_a", "DSPA", G, "Display trace A.", "9-19")
action("blank_a", "BLKA", G, "Blank trace A.", "9-19")
choice("active_trace", "ACTV", G, "Active trace.", "9-19", {"A": 0, "B": 1, "C": 2}, reply="int")
query("trace_b_mode", "TRB?", G, "Trace B mode: 0 WRITE, 1 FIX, 2 MIN HLD, 3+n ROLL AVG.", "9-19", reply="int")
action("write_b", "WRTB", G, "Trace B write mode.", "9-19")
action("fix_b", "FIXB", G, "Trace B fixed.", "9-19")
action("min_hold_b", "MINB", G, "Trace B min-hold.", "9-19")
number("roll_avg_b", "RAVB", G, "Trace B rolling averaging, 2..100.", "9-19", 2, 100, reply="int", query=False)
action("display_b", "DSPB", G, "Display trace B.", "9-20")
action("blank_b", "BLKB", G, "Blank trace B.", "9-20")
action("write_c", "WRTC", G, "Trace C write mode.", "9-20")
action("fix_c", "FIXC", G, "Trace C fixed.", "9-20")
action("c_eq_a_minus_b", "A-BC", G, "C = A - B (LOG).", "9-20")
action("c_eq_b_minus_a", "B-AC", G, "C = B - A (LOG).", "9-20")
action("c_eq_a_minus_b_lin", "A-BCL", G, "C = A - B (linear).", "9-20")
action("c_eq_b_minus_a_lin", "B-ACL", G, "C = B - A (linear).", "9-20")
action("c_eq_a_plus_b_lin", "A+BCL", G, "C = A + B (linear).", "9-20")
query("trace_c_mode", "TRC?", G, "Trace C mode (0 WRITE,1 FIX,2 A-B,3 B-A,4 A-B lin,5 B-A lin,6 A+B lin,7 NORM,8 DOMINANT,10+x curve fit,110+x fit pk).", "9-20", reply="int")
action("normalize_c", "NORMC", G, "Display trace C normalized.", "9-21")
action("dominant_c", "DOMIC", G, "Trace C normalized with luminous efficacy compensation.", "9-21")
number("curve_fit_c", "CVFTC", G, "Curve fit of trace C (dB).", "9-21", 0, 99, unit="dB", query=False, reply="int")
number("curve_fit_peak_c", "CVPKC", G, "Curve fit, mode-peak points only (dB).", "9-21", 0, 99, unit="dB", query=False, reply="int")
action("display_c", "DSPC", G, "Display trace C.", "9-21")
action("blank_c", "BLKC", G, "Blank trace C.", "9-21")
action("copy_a_to_b", "B=A", G, "Copy trace A to B.", "9-21")
action("copy_a_to_c", "C=A", G, "Copy trace A to C.", "9-21")
action("copy_b_to_a", "A=B", G, "Copy trace B to A.", "9-21")
action("copy_b_to_c", "C=B", G, "Copy trace B to C.", "9-21")
action("copy_c_to_a", "A=C", G, "Copy trace C to A.", "9-21")
action("copy_c_to_b", "B=C", G, "Copy trace C to B.", "9-21")

# ---------------------------------------------------------------- DISPLAY (9-22, 9-23)
G = "display"
action("normal_display", "NORMD", G, "Normal display mode.", "9-22")
action("split_display", "SPLIT", G, "2-split display mode.", "9-22")
action("three_d_display", "3D", G, "3-D display mode.", "9-23")
query("display_mode", "DISP?", G, "0 NORMAL, 1 SPLIT, 2 3D.", "9-22", reply="int")
choice("trace_a_updown", "ULTRA", G, "Trace A upper/lower in split display.", "9-22", {"lower": 0, "upper": 1}, reply="int")
choice("trace_b_updown", "ULTRB", G, "Trace B upper/lower in split display.", "9-22", {"lower": 0, "upper": 1}, reply="int")
choice("trace_c_updown", "ULTRC", G, "Trace C upper/lower in split display.", "9-22", {"lower": 0, "upper": 1}, reply="int")
onoff("upper_hold", "UHLD", G, "Fix upper trace scale after change.", "9-22", reply="int")
onoff("lower_hold", "LHLD", G, "Fix lower trace scale after change.", "9-22", reply="int")
number("angle_3d", "ANGLE", G, "3-D display angle, -50..50 step 10.", "9-23", -50, 50, unit="deg", reply="int")
action("recall_3d", "3DRCL", G, "Redisplay waveform group in 3-D mode.", "9-23")
number("z_scale_3d", "ZSCL", G, "Number of waveforms in 3-D display, 3..16.", "9-23", 3, 16, reply="int")
choice("memory_3d", "MEM", G, "Memory for 3-D display (1st/2nd).", "9-23", {"1st": 0, "2nd": 1}, reply="int")
action("label_clear", "LBLCL", G, "Clear all label strings.", "9-23")
number("noise_mask", "NMSK", G, "Hide waveforms below value (dBm, 0..-100; -999 = OFF).", "9-23", -100, 0, unit="dBm", special=(-999,), reply="int")
action("clear_traces", "CLR", G, "Clear trace A, B and C.", "9-23", query=None)
# LBL'text' takes a quoted string (<=50 chars): see Osa.set_label()

# ---------------------------------------------------------------- MEMORY (9-24)
G = "memory"
for t in "ABC":
    number(f"save_{t.lower()}_to_mem", f"SAVE{t}", G, f"Save trace {t} into memory 0..31.", "9-24", 0, 31, query=False, reply="int")
    number(f"recall_mem_to_{t.lower()}", f"RCL{t}", G, f"Recall memory 0..31 to trace {t}.", "9-24", 0, 31, query=False, reply="int")

# ---------------------------------------------------------------- PROGRAM (9-28)
G = "program"
number("exec_program", "EXEC", G, "Execute internal program 1..20.", "9-28", 1, 20, reply="int")
action("program_exit", "PREXT", G, "Pause a program.", "9-28")
number("delete_program", "PRDEL", G, "Delete program 1..20.", "9-28", 1, 20, query=False, reply="int")

# ---------------------------------------------------------------- SYSTEM (9-29, 9-30)
G = "system"
choice("wavelength_medium", "MESWL", G, "Measured wavelength in air (0) or vacuum (1).", "9-29", {"air": 0, "vacuum": 1}, reply="int")
number("wl_calibration", "WCAL", G, "Waveform absolute-value calibration (nm).", "9-29", 350.0, 1750.0, 3, "nm")
number("wl_shift", "WLSFT", G, "Waveform shift (nm).", "9-30", -5.0, 5.0, 2, "nm")
number("level_shift", "LVSFT", G, "Level shift (dB).", "9-30", -30.0, 30.0, 2, "dB")
onoff("auto_offset", "ATOFS", G, "AMP auto offset function.", "9-30", reply="int")
onoff("buzzer_click", "BZCLK", G, "Click sound.", "9-30", reply="int")
onoff("buzzer_warning", "BZWRN", G, "Alarm sound.", "9-30", reply="int")
number("default_color", "DEFCL", G, "Display color pattern 1..5.", "9-29", 1, 5, reply="int")
query("date", "DATE?", G, "Current YR, MO, DY. (set syntax unverified, use send()).", "9-29")
query("time", "TIME?", G, "Current HH:MM. (set syntax unverified, use send()).", "9-29")

# ---------------------------------------------------------------- ADVANCE / power meter / optical output (9-30, 9-31)
G = "advance"
action("power_meter_repeat", "PMPRT", G, "Power meter: repeat measurement.", "9-30")
action("power_meter_single", "PMSGL", G, "Power meter: single measurement.", "9-30")
action("power_meter_stop", "PMSTP", G, "Power meter: stop.", "9-30")
query("power_meter_status", "PMST?", G, "0 STOP, 1 SINGLE, 2 REPEAT.", "9-30", reply="int")
choice("power_meter_area", "AREA", G, "Measuring range.", "9-30",
       {"full": 0, "350-700nm": 1, "600-1000nm": 2, "1000-1750nm": 3}, reply="int")
onoff("power_meter_relative", "REL", G, "Relative (1) / absolute (0) value.", "9-31", reply="int")
action("power_meter_max_min_reset", "PMRST", G, "Reset max/min values.", "9-31")
choice("power_meter_unit", "PMUNT", G, "Power meter unit dBm or W.", "9-31", {"dBm": 0, "W": 1}, reply="int")
number("optical_output_wl", "OUTWL", G, "Optical output wavelength (nm).", "9-31", 350.0, 1750.0, 3, "nm")
number("optical_output_bw", "OUTBW", G, "Optical output bandwidth (nm), 1-2-5 steps.", "9-31", 0.05, 10.0, 2, "nm")
number("beam_align", "BMALN", G, "Fine adjustment of Y position at optical output.", "9-31", -200, 200, reply="int")

# ---------------------------------------------------------------- OTHERS (9-32 .. 9-35)
G = "other"
action("initialize_data", "INIT", G, "Initialize nonvolatile data except program/memory.", "9-33", query=None)
onoff("header", "HD", G, "Append header to talker data (default off).", "9-33", reply="int")
choice("log_digits", "LDTDIG", G, "Decimal digits of log level data: 2 or 3 (2 after power-on).", "9-34", {2: 2, 3: 3}, reply="int")
choice("string_delimiter", "SD", G, "String delimiter: 0 = ',', 1 = CRLF.", "9-32", {",": 0, "CRLF": 1}, reply="int")
choice("block_delimiter", "BD", G, "Block delimiter: 0 = CRLF+EOI, 1 = LF+EOI.", "9-32", {"CRLF+EOI": 0, "LF+EOI": 1}, reply="int")
onoff("service_request", "SRQ", G, "Enable (1) / inhibit (0) service request; default off.", "9-32", reply="int")
number("srq_mask", "SRMSK", G, "SRQ mask bits 0..255.", "9-32", 0, 255, reply="int")
onoff("help_display", "HELP", G, "Explanatory statement display.", "9-32", reply="int")
onoff("coarse_key", "CRS", G, "[COARSE] key of rotary knob.", "9-32", reply="int")
query("warning_number", "WARN?", G, "Most recent warning error number.", "9-35", reply="str")
query("power_meter_result", "PMTR?", G, "Power meter measurement result.", "9-35")
query("power_meter_max", "MAXP?", G, "Power meter MAX power.", "9-35")
query("power_meter_min", "MINP?", G, "Power meter MIN power.", "9-35")

# Waveform data requests (LDATA, WDATA, ...) have optional R<a>-R<b> ranges and are implemented in osa.py.

COMMANDS: dict[str, Cmd] = {c.name: c for c in _TABLE}
BY_CODE: dict[str, Cmd] = {}
for _c in _TABLE:
    BY_CODE.setdefault(_c.code, _c)

# Sensitivity set codes (differ from the numbers SENS? returns)
SENS_SET = {"norm_hold": "SNHD", "norm_auto": "SNAT", "high1": "SHI1", "high2": "SHI2", "high3": "SHI3"}
SENS_REPLY = {1: "high1", 2: "high2", 3: "high3", 4: "norm_hold", 5: "norm_auto"}
# Light-mode set codes
LIGHT_SET = {"cw": "CLMES", "pulse": "PLMES"}

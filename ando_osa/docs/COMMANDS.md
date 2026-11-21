# AQ6315 command reference (generated from src/ando_osa/commands.py)

Page = manual chapter 9 page. `set_` methods validate ranges before sending.

## sweep

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `auto_sweep()` | `AUTO` | `` |  | 9-5 | Start an auto sweep. |
| `repeat_sweep()` | `RPT` | `` |  | 9-5 | Start a repeat sweep. |
| `single_sweep()` | `SGL` | `` |  | 9-5 | Start a single sweep. |
| `segment_measure()` | `SMEAS` | `` |  | 9-5 | Measure according to the set sampling count (segment measure). |
| `stop_sweep()` | `STP` | `` |  | 9-5 | Stop a sweep. |
| `get_sweep_status()` | `SWEEP` | `SWEEP?` |  | 9-5 | Measurement status: 0 STOP,1 SINGLE,2 REPEAT,3 AUTO,4 SEGMENT MEASURE. |
| `set_seg_points(x)` / `get_seg_points()` | `SEGP<x>` | `SEGP?` | 1 .. 1001  | 9-5 | Sampling count for SEGMENT MEASURE. |
| `set_sweep_mkr_l1_l2(x)` / `get_sweep_mkr_l1_l2()` | `SWPM<x>` | `SWPM?` | off, on | 9-5 | Marker-to-marker sweep (L1-L2) on/off. |
| `set_sweep_interval(x)` / `get_sweep_interval()` | `SWPI<x>` | `SWPI?` | 0 .. 99999 s | 9-5 | Time from sweep start to next sweep start in repeat mode (s); 0 = minimum. |

## center

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `set_center_wl(x)` / `get_center_wl()` | `CTRWL<x>` | `CTRWL?` | 350.0 .. 1750.0 nm | 9-6 | Center wavelength. |
| `set_start_wl(x)` / `get_start_wl()` | `STAWL<x>` | `STAWL?` | -400.0 .. 1750.0 nm | 9-6 | Measurement start wavelength. |
| `set_stop_wl(x)` / `get_stop_wl()` | `STPWL<x>` | `STPWL?` | 350.0 .. 2500.0 nm | 9-6 | Measurement stop wavelength. |
| `peak_to_center()` | `CTR=P` | `` |  | 9-6 | Set waveform peak wavelength as center wavelength. |
| `set_auto_center(x)` / `get_auto_center()` | `ATCTR<x>` | `ATCTR?` | off, on | 9-6 | Peak->center at each sweep on/off. |

## span

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `set_span(x)` / `get_span()` | `SPAN<x>` | `SPAN?` | 1.0 .. 1500.0 nm (or (0,)) | 9-6 | Span (0 allowed = zero-span). |
| `marker_span()` | `SPN=W` | `` |  | 9-6 | Set span from the delta-lambda (L1-L2) marker range. |
| `set_zero_span_sweep_time(x)` / `get_zero_span_sweep_time()` | `ZSWPT<x>` | `ZSWPT?` | 0 .. 50 s | 9-6 | Sweep time at 0 nm span; 0 = minimum. |

## level

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `set_ref_level(x)` / `get_ref_level()` | `REFL<x>` | `REFL?` | -90.0 .. 20.0 dBm | 9-7 | Reference level in LOG mode. |
| `set_ref_level_pw(x)` | `REFLP<x>` | `` | 1.0 .. 999.0 pW | 9-7 | Ref level, linear (pW). 1.00-9.99 step .01, 10.0-99.9 step .1, 100-999 step 1. |
| `set_ref_level_nw(x)` | `REFLN<x>` | `` | 1.0 .. 999.0 nW | 9-7 | Ref level, linear (nW). |
| `set_ref_level_uw(x)` | `REFLU<x>` | `` | 1.0 .. 999.0 uW | 9-7 | Ref level, linear (uW). |
| `set_ref_level_mw(x)` | `REFLM<x>` | `` | 1.0 .. 100.0 mW | 9-7 | Ref level, linear (mW); 10.0-100 step 0.1. |
| `get_ref_level_any()` | `REFL` | `REFL?` |  | 9-7 | Ref level as returned in current scale: dBm number, or 'PW/NW/UW/MW <value>'. |
| `set_level_scale(x)` / `get_level_scale()` | `LSCL<x>` | `LSCL?` | 0.1 .. 10.0 dB/div | 9-7 | Level axis scale (dB/DIV); in LIN scale query returns 0. |
| `set_base_level(x)` / `get_base_level()` | `BASL<x>` | `BASL?` | 0.0 .. 999.0 mW | 9-7 | Bottom scale value in linear scale mode (= REF LEVEL x 0.9 max). |
| `peak_to_ref()` | `REF=P` | `` |  | 9-7 | Set peak level as reference level. |
| `set_auto_ref_level(x)` / `get_auto_ref_level()` | `ATREF<x>` | `ATREF?` | off, on | 9-7 | Peak->ref level at each sweep on/off. |
| `set_level_unit(x)` / `get_level_unit()` | `LSUNT<x>` | `LSUNT?` | dBm, dBm/nm | 9-8 | Level axis unit: dBm(W) or dBm/nm (W/nm). |
| `set_sublog(x)` / `get_sublog()` | `SLOG<x>` | `SLOG?` | 0.1 .. 10.0  | 9-8 | Subscale (LOG), dB/div. |
| `set_sublin(x)` / `get_sublin()` | `SLIN<x>` | `SLIN?` | 0.005 .. 1.25  | 9-8 | Subscale (LINEAR), step 0.005. |
| `set_sub_scale_db_km(x)` / `get_sub_scale_db_km()` | `SKM<x>` | `SKM?` | 0.1 .. 10.0  | 9-8 | Subscale in dB/km. |
| `set_sub_scale_pct(x)` / `get_sub_scale_pct()` | `SPS<x>` | `SPS?` | 0.5 .. 125.0  | 9-8 | Subscale in %/D. |
| `set_level_offset(x)` / `get_level_offset()` | `LOFST<x>` | `LOFST?` | -99.9 .. 99.9 dB | 9-8 | Offset level of the scale (dB). |
| `set_level_offset_km(x)` / `get_level_offset_km()` | `LOFSKM<x>` | `LOFSKM?` | -99.9 .. 99.9 dB/km | 9-8 | Offset of subscale (dB/km). |
| `set_scale_min_lin(x)` / `get_scale_min_lin()` | `SMIN<x>` | `SMIN?` | 0.0 .. 12.5  | 9-8 | Bottom scale in Linear subscale mode (x10 /DIV). |
| `set_scale_min_pct(x)` / `get_scale_min_pct()` | `SMINP<x>` | `SMINP?` | 0.0 .. 1250.0  | 9-8 | Bottom scale in % subscale mode (x10 /DIV). |
| `set_fiber_length(x)` / `get_fiber_length()` | `LNGT<x>` | `LNGT?` | 0.001 .. 99.999 km | 9-8 | Optical fiber length. |
| `set_auto_subscale(x)` / `get_auto_subscale()` | `ATSCL<x>` | `ATSCL?` | off, on | 9-8 | Auto scaling display on/off. |

## setup

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `set_resolution(x)` / `get_resolution()` | `RESLN<x>` | `RESLN?` | 0.05 .. 10.0 nm | 9-9 | Resolution (1-2-5 steps: 0.05 ... 10.0). |
| `set_sensitivity(x)` / `get_sensitivity()` | `SENS<x>` | `SENS?` | norm_hold, norm_auto, high1, high2, high3 | 9-9 | Measuring sensitivity. Set codes: SNHD, SNAT, SHI1, SHI2, SHI3; SENS? returns 1..5. |
| `set_averaging(x)` / `get_averaging()` | `AVG<x>` | `AVG?` | 1 .. 1000  | 9-9 | Number of averages. |
| `set_sampling_points(x)` / `get_sampling_points()` | `SMPL<x>` | `SMPL?` | 11 .. 1001  | 9-9 | Sampling points. |
| `set_light_mode(x)` / `get_light_mode()` | `CWPLS<x>` | `CWPLS?` | pulse, cw | 9-10 | CW (CLMES) or PULSE (PLMES) light measurement; CWPLS? returns 0 pulse / 1 CW. |
| `get_chop_light_mode()` | `PLMOD` | `PLMOD?` |  | 9-10 | Chop-light mode: 0 LPF, 1 EXT TRG, 2+hold time = PEAK HOLD. |
| `lpf_mode()` | `LPF` | `` |  | 9-10 | Chop-light measurement via lowpass filter. |
| `set_peak_hold_ms(x)` | `PKHLD<x>` | `` | 1 .. 9999 ms | 9-10 | Chop-light measurement via peak hold; hold time ms. |
| `ext_trigger_mode()` | `EXTRG` | `` |  | 9-10 | Chop-light measurement via external trigger. |
| `set_monochromator(x)` / `get_monochromator()` | `MONO<x>` | `MONO?` | single, double | 9-10 | Single or double monochromator. |
| `set_chop_source(x)` / `get_chop_source()` | `CHOP<x>` | `CHOP?` | internal, external | 9-10 | Chopping: internal or external. |

## marker

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `set_marker_wl(x)` | `WMKR<x>` | `` | -400.0 .. 2500.0 nm | 9-11 | Moving marker to wavelength. |
| `set_marker_thz(x)` | `FMKR<x>` | `` | 110.0 .. 9999.999 THz | 9-11 | Moving marker to frequency. |
| `get_marker()` | `MKR` | `MKR?` |  | 9-11 | Wavelength/frequency and level at moving marker (Table 9-4, 9-39). |
| `marker_to_center()` | `CTR=M` | `` |  | 9-11 | Moving marker wavelength -> center wavelength. |
| `marker_to_ref()` | `REF=M` | `` |  | 9-11 | Moving marker level -> reference level. |
| `set_marker1()` | `MKR1` | `` |  | 9-11 | Set moving marker to fixed marker 1. |
| `set_marker2()` | `MKR2` | `` |  | 9-11 | Set moving marker to fixed marker 2. |
| `get_marker1()` | `MKR1` | `MKR1?` |  | 9-11 | Wavelength and level at fixed marker 1. |
| `get_marker2()` | `MKR2` | `MKR2?` |  | 9-11 | Wavelength and level at fixed marker 2. |
| `marker_clear()` | `MKCL` | `` |  | 9-11 | Clear moving marker, fixed markers and marker values. |
| `set_marker_unit(x)` / `get_marker_unit()` | `MKUNT<x>` | `MKUNT?` | nm, THz | 9-11 | Marker value unit nm or THz. |
| `set_line_marker1_nm(x)` / `get_line_marker1_nm()` | `L1MK<x>` | `L1MK?` | -400.0 .. 2500.0 nm | 9-11 | Wavelength line marker 1. |
| `set_line_marker1_thz(x)` | `L1FMK<x>` | `` | 110.0 .. 9999.999 THz | 9-11 | Wavelength line marker 1 (frequency). |
| `set_line_marker2_nm(x)` / `get_line_marker2_nm()` | `L2MK<x>` | `L2MK?` | -400.0 .. 2500.0 nm | 9-11 | Wavelength line marker 2. |
| `set_line_marker2_thz(x)` | `L2FMK<x>` | `` | 110.0 .. 9999.999 THz | 9-11 | Wavelength line marker 2 (frequency). |
| `set_line_marker3_dbm(x)` / `get_line_marker3_dbm()` | `L3DBM<x>` | `L3MK?` | -150.0 .. 40.0 dBm | 9-12 | Level line marker 3 (LOG). |
| `set_line_marker3_db(x)` | `L3DB<x>` | `` | -139.9 .. 139.9 dB | 9-12 | Level line marker 3 (SUBLOG). |
| `set_line_marker4_dbm(x)` / `get_line_marker4_dbm()` | `L4DBM<x>` | `L4MK?` | -150.0 .. 40.0 dBm | 9-12 | Level line marker 4 (LOG). |
| `set_line_marker4_db(x)` | `L4DB<x>` | `` | -139.9 .. 139.9 dB | 9-12 | Level line marker 4 (SUBLOG). |
| `marker_l1l2_to_span()` | `SP=LM` | `` |  | 9-12 | Set the L1-L2 section as sweep range. |
| `set_search_l1_l2(x)` / `get_search_l1_l2()` | `SRLMK<x>` | `SRLMK?` | off, on | 9-12 | Peak detection restricted to L1-L2 on/off. |
| `line_marker_clear()` | `LMKCL` | `` |  | 9-12 | Clear line markers and line marker values. |

## search

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `peak_search()` | `PKSR` | `` |  | 9-12 | Detect MAX value of level. |
| `bottom_search()` | `BTSR` | `` |  | 9-12 | Detect MIN value of level. |
| `next_search()` | `NSR` | `` |  | 9-12 | Next largest (or next smallest) value. |
| `next_search_right()` | `NSRR` | `` |  | 9-12 | Largest (smallest) value to the right of moving marker. |
| `next_search_left()` | `NSRL` | `` |  | 9-12 | Largest (smallest) value to the left of moving marker. |
| `get_search_mode()` | `PKSR` | `PKSR?` |  | 9-12 | 0 = BOTTOM, 1 = PEAK (last search type). |
| `set_auto_search(x)` / `get_auto_search()` | `ATSR<x>` | `ATSR?` | off, on | 9-12 | Automatic peak/bottom detection after sweep on/off. |
| `set_mode_diff_search(x)` / `get_mode_diff_search()` | `MODIF<x>` | `MODIF?` | 0.0 .. 50.0 dB | 9-12 | Level difference for mode judgment (dB). |

## analysis

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `set_spec_width_method(x)` / `get_spec_width_method()` | `SW<x>` | `SW?` | envelope, thresh, rms, peak_rms, notch | 9-13 | Spectrum width method: ENVELOPE 0, THRESH 1, RMS 2, PEAK RMS 3, NOTCH 4. |
| `spec_width_envelope()` | `SWENV` | `` |  | 9-13 | Measure spectrum width, Envelope method. |
| `set_env_th1(x)` / `get_env_th1()` | `ENVT1<x>` | `ENVT1?` | 0.1 .. 10.0 dB | 9-13 | Envelope: threshold (dB). |
| `set_env_th2(x)` / `get_env_th2()` | `ENVT2<x>` | `ENVT2?` | 0.1 .. 30.0 dB | 9-13 | Envelope: truncation limit (dB). |
| `set_env_k(x)` / `get_env_k()` | `ENVK<x>` | `ENVK?` | 1.0 .. 10.0  | 9-13 | Envelope: magnification ratio K. |
| `spec_width_thresh()` | `SWTHR` | `` |  | 9-13 | Measure spectrum width, Threshold method. |
| `set_thresh_th(x)` / `get_thresh_th()` | `THRTH<x>` | `THRTH?` | 0.1 .. 50.0 dB | 9-13 | Threshold method: threshold (dB). |
| `set_thresh_k(x)` / `get_thresh_k()` | `THRK<x>` | `THRK?` | 1.0 .. 10.0  | 9-13 | Threshold method: magnification ratio K. |
| `set_mode_fit(x)` / `get_mode_fit()` | `MODFT<x>` | `MODFT?` | threshold_level, mode_peak | 9-13 | Mode-fit marker: 1 = mode peak, 0 = threshold level position. |
| `spec_width_rms()` | `SWRMS` | `` |  | 9-14 | Measure spectrum width, RMS method. |
| `set_rms_th(x)` / `get_rms_th()` | `RMSTH<x>` | `RMSTH?` | 0.1 .. 30.0 dB | 9-14 | RMS: truncation limit (dB). |
| `set_rms_k(x)` / `get_rms_k()` | `RMSK<x>` | `RMSK?` | 1.0 .. 10.0  | 9-14 | RMS: magnification ratio K. |
| `spec_width_peak_rms()` | `SWPRM` | `` |  | 9-14 | Measure spectrum width, Peak RMS method. |
| `set_peak_rms_th(x)` / `get_peak_rms_th()` | `PRMTH<x>` | `PRMTH?` | 0.1 .. 30.0 dB | 9-14 | Peak RMS: truncation limit (dB). |
| `set_peak_rms_k(x)` / `get_peak_rms_k()` | `PRMK<x>` | `PRMK?` | 1.0 .. 10.0  | 9-14 | Peak RMS: magnification ratio K. |
| `spec_width_notch()` | `SWNCH` | `` |  | 9-14 | Measure the notch width. |
| `set_notch_th(x)` / `get_notch_th()` | `NCHTH<x>` | `NCHTH?` | 0.1 .. 50.0 dB | 9-14 | Notch width threshold (dB). |
| `set_smsr_ref(x)` / `get_smsr_ref()` | `SMSR<x>` | `SMSR?` | 1, 2 | 9-14 | Reference to measure side-mode suppress ratio (1 or 2). Send 'SMSR1'/'SMSR2'. |
| `set_smsr_mask(x)` / `get_smsr_mask()` | `SSMSK<x>` | `SSMSK?` | 0.0 .. 99.99 nm | 9-14 | SMSR1 mask range around peak (nm). |
| `analyze_power()` | `PWR` | `` |  | 9-15 | Measure marker-to-marker power. |
| `set_power_offset(x)` / `get_power_offset()` | `POFS<x>` | `POFS?` | -10.0 .. 10.0 dB | 9-15 | Compensation for marker-to-marker power (dB). |
| `analyze_fp_ld()` | `FPAN` | `` |  | 9-15 | Analyze Fabry-Perot laser diode. |
| `analyze_dfb_ld()` | `DFBAN` | `` |  | 9-15 | Analyze DFB laser diode. |
| `analyze_led()` | `LEDAN` | `` |  | 9-15 | Analyze light emitting diode. |
| `analyze_color()` | `COLAN` | `` |  | 9-15 | Analyze the colors. |
| `analyze_edfa_nf()` | `EDNF` | `` |  | 9-15 | Calculate EDFA noise figure. |
| `set_nf_offset_in(x)` / `get_nf_offset_in()` | `OFIN<x>` | `OFIN?` | -99.99 .. 99.99 dB | 9-15 | Offset of signal light (dB). |
| `set_nf_offset_out(x)` / `get_nf_offset_out()` | `OFOUT<x>` | `OFOUT?` | -99.99 .. 99.99 dB | 9-15 | Offset of output light (dB). |
| `set_nf_plus_mask(x)` / `get_nf_plus_mask()` | `PLMSK<x>` | `PLMSK?` | 0.0 .. 10.0 nm | 9-15 | Mask range right to peak (nm). |
| `set_nf_minus_mask(x)` / `get_nf_minus_mask()` | `MIMSK<x>` | `MIMSK?` | 0.0 .. 10.0 nm | 9-15 | Mask range left to peak (nm). |
| `set_nf_curve_fit(x)` / `get_nf_curve_fit()` | `EDFCVF<x>` | `EDFCVF?` | gaussian, lorenzian, poly3, poly4, poly5 | 9-16 | NF curve fit type. |
| `set_nf_fit_threshold(x)` / `get_nf_fit_threshold()` | `EDFTH<x>` | `EDFTH?` | 0.1 .. 99.9 dB | 9-16 | Curve fitting threshold (dB). |
| `analyze_wdm()` | `WDMAN` | `` |  | 9-16 | Analyze the WDM. |
| `set_wdm_display(x)` / `get_wdm_display()` | `WDMOS<x>` | `WDMOS?` | offset, spacing | 9-16 | WDM list display: OFFSET 0 / SPACING 1. |
| `wdm_ref_highest()` | `WDMRH` | `` |  | 9-16 | Reference = highest channel peak. |
| `set_wdm_ref_wl(x)` / `get_wdm_ref_wl()` | `WDMRW<x>` | `WDMRW?` | 350.0 .. 1750.0 nm | 9-16 | Reference = channel peak closest to wavelength. |
| `set_wdm_ref_channel(x)` / `get_wdm_ref_channel()` | `WDMRN<x>` | `WDMRN?` | 1 .. 99  | 9-16 | Reference = n-th channel peak. |
| `set_wdm_threshold(x)` / `get_wdm_threshold()` | `WDMTH<x>` | `WDMTH?` | 0.1 .. 50.0 dB | 9-16 | Channel-peak threshold (dB). |
| `set_wdm_max_channels(x)` / `get_wdm_max_channels()` | `WDMMAX<x>` | `WDMMAX?` | 1 .. 99  | 9-16 | Maximum number of channel peaks. |
| `set_wdm_mode_diff(x)` / `get_wdm_mode_diff()` | `WDMDIF<x>` | `WDMDIF?` | 0.0 .. 50.0 dB | 9-16 | Min. top-to-bottom difference for channel peak detection (dB). |
| `set_auto_analysis(x)` / `get_auto_analysis()` | `ATANA<x>` | `ATANA?` | off, on | 9-17 | Auto-execute selected analysis after sweep. |
| `get_analysis()` | `ANA` | `ANA?` |  | 9-34 | Analysis result (format depends on analysis type; Table 9-4, 9-40..9-44). |

## trace

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `get_trace_a_mode()` | `TRA` | `TRA?` |  | 9-19 | Trace A mode: 0 WRITE, 1 FIX, 2 MAX HLD, 3+n ROLL AVG. |
| `write_a()` | `WRTA` | `` |  | 9-19 | Trace A write mode. |
| `fix_a()` | `FIXA` | `` |  | 9-19 | Trace A fixed. |
| `max_hold_a()` | `MAXA` | `` |  | 9-19 | Trace A max-hold. |
| `set_roll_avg_a(x)` | `RAVA<x>` | `` | 2 .. 100  | 9-19 | Trace A sequential (rolling) averaging, 2..100. |
| `display_a()` | `DSPA` | `` |  | 9-19 | Display trace A. |
| `blank_a()` | `BLKA` | `` |  | 9-19 | Blank trace A. |
| `set_active_trace(x)` / `get_active_trace()` | `ACTV<x>` | `ACTV?` | A, B, C | 9-19 | Active trace. |
| `get_trace_b_mode()` | `TRB` | `TRB?` |  | 9-19 | Trace B mode: 0 WRITE, 1 FIX, 2 MIN HLD, 3+n ROLL AVG. |
| `write_b()` | `WRTB` | `` |  | 9-19 | Trace B write mode. |
| `fix_b()` | `FIXB` | `` |  | 9-19 | Trace B fixed. |
| `min_hold_b()` | `MINB` | `` |  | 9-19 | Trace B min-hold. |
| `set_roll_avg_b(x)` | `RAVB<x>` | `` | 2 .. 100  | 9-19 | Trace B rolling averaging, 2..100. |
| `display_b()` | `DSPB` | `` |  | 9-20 | Display trace B. |
| `blank_b()` | `BLKB` | `` |  | 9-20 | Blank trace B. |
| `write_c()` | `WRTC` | `` |  | 9-20 | Trace C write mode. |
| `fix_c()` | `FIXC` | `` |  | 9-20 | Trace C fixed. |
| `c_eq_a_minus_b()` | `A-BC` | `` |  | 9-20 | C = A - B (LOG). |
| `c_eq_b_minus_a()` | `B-AC` | `` |  | 9-20 | C = B - A (LOG). |
| `c_eq_a_minus_b_lin()` | `A-BCL` | `` |  | 9-20 | C = A - B (linear). |
| `c_eq_b_minus_a_lin()` | `B-ACL` | `` |  | 9-20 | C = B - A (linear). |
| `c_eq_a_plus_b_lin()` | `A+BCL` | `` |  | 9-20 | C = A + B (linear). |
| `get_trace_c_mode()` | `TRC` | `TRC?` |  | 9-20 | Trace C mode (0 WRITE,1 FIX,2 A-B,3 B-A,4 A-B lin,5 B-A lin,6 A+B lin,7 NORM,8 DOMINANT,10+x curve fit,110+x fit pk). |
| `normalize_c()` | `NORMC` | `` |  | 9-21 | Display trace C normalized. |
| `dominant_c()` | `DOMIC` | `` |  | 9-21 | Trace C normalized with luminous efficacy compensation. |
| `set_curve_fit_c(x)` | `CVFTC<x>` | `` | 0 .. 99 dB | 9-21 | Curve fit of trace C (dB). |
| `set_curve_fit_peak_c(x)` | `CVPKC<x>` | `` | 0 .. 99 dB | 9-21 | Curve fit, mode-peak points only (dB). |
| `display_c()` | `DSPC` | `` |  | 9-21 | Display trace C. |
| `blank_c()` | `BLKC` | `` |  | 9-21 | Blank trace C. |
| `copy_a_to_b()` | `B=A` | `` |  | 9-21 | Copy trace A to B. |
| `copy_a_to_c()` | `C=A` | `` |  | 9-21 | Copy trace A to C. |
| `copy_b_to_a()` | `A=B` | `` |  | 9-21 | Copy trace B to A. |
| `copy_b_to_c()` | `C=B` | `` |  | 9-21 | Copy trace B to C. |
| `copy_c_to_a()` | `A=C` | `` |  | 9-21 | Copy trace C to A. |
| `copy_c_to_b()` | `B=C` | `` |  | 9-21 | Copy trace C to B. |

## display

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `normal_display()` | `NORMD` | `` |  | 9-22 | Normal display mode. |
| `split_display()` | `SPLIT` | `` |  | 9-22 | 2-split display mode. |
| `three_d_display()` | `3D` | `` |  | 9-23 | 3-D display mode. |
| `get_display_mode()` | `DISP` | `DISP?` |  | 9-22 | 0 NORMAL, 1 SPLIT, 2 3D. |
| `set_trace_a_updown(x)` / `get_trace_a_updown()` | `ULTRA<x>` | `ULTRA?` | lower, upper | 9-22 | Trace A upper/lower in split display. |
| `set_trace_b_updown(x)` / `get_trace_b_updown()` | `ULTRB<x>` | `ULTRB?` | lower, upper | 9-22 | Trace B upper/lower in split display. |
| `set_trace_c_updown(x)` / `get_trace_c_updown()` | `ULTRC<x>` | `ULTRC?` | lower, upper | 9-22 | Trace C upper/lower in split display. |
| `set_upper_hold(x)` / `get_upper_hold()` | `UHLD<x>` | `UHLD?` | off, on | 9-22 | Fix upper trace scale after change. |
| `set_lower_hold(x)` / `get_lower_hold()` | `LHLD<x>` | `LHLD?` | off, on | 9-22 | Fix lower trace scale after change. |
| `set_angle_3d(x)` / `get_angle_3d()` | `ANGLE<x>` | `ANGLE?` | -50 .. 50 deg | 9-23 | 3-D display angle, -50..50 step 10. |
| `recall_3d()` | `3DRCL` | `` |  | 9-23 | Redisplay waveform group in 3-D mode. |
| `set_z_scale_3d(x)` / `get_z_scale_3d()` | `ZSCL<x>` | `ZSCL?` | 3 .. 16  | 9-23 | Number of waveforms in 3-D display, 3..16. |
| `set_memory_3d(x)` / `get_memory_3d()` | `MEM<x>` | `MEM?` | 1st, 2nd | 9-23 | Memory for 3-D display (1st/2nd). |
| `label_clear()` | `LBLCL` | `` |  | 9-23 | Clear all label strings. |
| `set_noise_mask(x)` / `get_noise_mask()` | `NMSK<x>` | `NMSK?` | -100 .. 0 dBm (or (-999,)) | 9-23 | Hide waveforms below value (dBm, 0..-100; -999 = OFF). |
| `clear_traces()` | `CLR` | `` |  | 9-23 | Clear trace A, B and C. |

## memory

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `set_save_a_to_mem(x)` | `SAVEA<x>` | `` | 0 .. 31  | 9-24 | Save trace A into memory 0..31. |
| `set_recall_mem_to_a(x)` | `RCLA<x>` | `` | 0 .. 31  | 9-24 | Recall memory 0..31 to trace A. |
| `set_save_b_to_mem(x)` | `SAVEB<x>` | `` | 0 .. 31  | 9-24 | Save trace B into memory 0..31. |
| `set_recall_mem_to_b(x)` | `RCLB<x>` | `` | 0 .. 31  | 9-24 | Recall memory 0..31 to trace B. |
| `set_save_c_to_mem(x)` | `SAVEC<x>` | `` | 0 .. 31  | 9-24 | Save trace C into memory 0..31. |
| `set_recall_mem_to_c(x)` | `RCLC<x>` | `` | 0 .. 31  | 9-24 | Recall memory 0..31 to trace C. |

## program

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `set_exec_program(x)` / `get_exec_program()` | `EXEC<x>` | `EXEC?` | 1 .. 20  | 9-28 | Execute internal program 1..20. |
| `program_exit()` | `PREXT` | `` |  | 9-28 | Pause a program. |
| `set_delete_program(x)` | `PRDEL<x>` | `` | 1 .. 20  | 9-28 | Delete program 1..20. |

## system

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `set_wavelength_medium(x)` / `get_wavelength_medium()` | `MESWL<x>` | `MESWL?` | air, vacuum | 9-29 | Measured wavelength in air (0) or vacuum (1). |
| `set_wl_calibration(x)` / `get_wl_calibration()` | `WCAL<x>` | `WCAL?` | 350.0 .. 1750.0 nm | 9-29 | Waveform absolute-value calibration (nm). |
| `set_wl_shift(x)` / `get_wl_shift()` | `WLSFT<x>` | `WLSFT?` | -5.0 .. 5.0 nm | 9-30 | Waveform shift (nm). |
| `set_level_shift(x)` / `get_level_shift()` | `LVSFT<x>` | `LVSFT?` | -30.0 .. 30.0 dB | 9-30 | Level shift (dB). |
| `set_auto_offset(x)` / `get_auto_offset()` | `ATOFS<x>` | `ATOFS?` | off, on | 9-30 | AMP auto offset function. |
| `set_buzzer_click(x)` / `get_buzzer_click()` | `BZCLK<x>` | `BZCLK?` | off, on | 9-30 | Click sound. |
| `set_buzzer_warning(x)` / `get_buzzer_warning()` | `BZWRN<x>` | `BZWRN?` | off, on | 9-30 | Alarm sound. |
| `set_default_color(x)` / `get_default_color()` | `DEFCL<x>` | `DEFCL?` | 1 .. 5  | 9-29 | Display color pattern 1..5. |
| `get_date()` | `DATE` | `DATE?` |  | 9-29 | Current YR, MO, DY. (set syntax unverified, use send()). |
| `get_time()` | `TIME` | `TIME?` |  | 9-29 | Current HH:MM. (set syntax unverified, use send()). |

## advance

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `power_meter_repeat()` | `PMPRT` | `` |  | 9-30 | Power meter: repeat measurement. |
| `power_meter_single()` | `PMSGL` | `` |  | 9-30 | Power meter: single measurement. |
| `power_meter_stop()` | `PMSTP` | `` |  | 9-30 | Power meter: stop. |
| `get_power_meter_status()` | `PMST` | `PMST?` |  | 9-30 | 0 STOP, 1 SINGLE, 2 REPEAT. |
| `set_power_meter_area(x)` / `get_power_meter_area()` | `AREA<x>` | `AREA?` | full, 350-700nm, 600-1000nm, 1000-1750nm | 9-30 | Measuring range. |
| `set_power_meter_relative(x)` / `get_power_meter_relative()` | `REL<x>` | `REL?` | off, on | 9-31 | Relative (1) / absolute (0) value. |
| `power_meter_max_min_reset()` | `PMRST` | `` |  | 9-31 | Reset max/min values. |
| `set_power_meter_unit(x)` / `get_power_meter_unit()` | `PMUNT<x>` | `PMUNT?` | dBm, W | 9-31 | Power meter unit dBm or W. |
| `set_optical_output_wl(x)` / `get_optical_output_wl()` | `OUTWL<x>` | `OUTWL?` | 350.0 .. 1750.0 nm | 9-31 | Optical output wavelength (nm). |
| `set_optical_output_bw(x)` / `get_optical_output_bw()` | `OUTBW<x>` | `OUTBW?` | 0.05 .. 10.0 nm | 9-31 | Optical output bandwidth (nm), 1-2-5 steps. |
| `set_beam_align(x)` / `get_beam_align()` | `BMALN<x>` | `BMALN?` | -200 .. 200  | 9-31 | Fine adjustment of Y position at optical output. |

## other

| Python | Sends | Query | Range / options | Page | Description |
|---|---|---|---|---|---|
| `initialize_data()` | `INIT` | `` |  | 9-33 | Initialize nonvolatile data except program/memory. |
| `set_header(x)` / `get_header()` | `HD<x>` | `HD?` | off, on | 9-33 | Append header to talker data (default off). |
| `set_log_digits(x)` / `get_log_digits()` | `LDTDIG<x>` | `LDTDIG?` | 2, 3 | 9-34 | Decimal digits of log level data: 2 or 3 (2 after power-on). |
| `set_string_delimiter(x)` / `get_string_delimiter()` | `SD<x>` | `SD?` | ,, CRLF | 9-32 | String delimiter: 0 = ',', 1 = CRLF. |
| `set_block_delimiter(x)` / `get_block_delimiter()` | `BD<x>` | `BD?` | CRLF+EOI, LF+EOI | 9-32 | Block delimiter: 0 = CRLF+EOI, 1 = LF+EOI. |
| `set_service_request(x)` / `get_service_request()` | `SRQ<x>` | `SRQ?` | off, on | 9-32 | Enable (1) / inhibit (0) service request; default off. |
| `set_srq_mask(x)` / `get_srq_mask()` | `SRMSK<x>` | `SRMSK?` | 0 .. 255  | 9-32 | SRQ mask bits 0..255. |
| `set_help_display(x)` / `get_help_display()` | `HELP<x>` | `HELP?` | off, on | 9-32 | Explanatory statement display. |
| `set_coarse_key(x)` / `get_coarse_key()` | `CRS<x>` | `CRS?` | off, on | 9-32 | [COARSE] key of rotary knob. |
| `get_warning_number()` | `WARN` | `WARN?` |  | 9-35 | Most recent warning error number. |
| `get_power_meter_result()` | `PMTR` | `PMTR?` |  | 9-35 | Power meter measurement result. |
| `get_power_meter_max()` | `MAXP` | `MAXP?` |  | 9-35 | Power meter MAX power. |
| `get_power_meter_min()` | `MINP` | `MINP?` |  | 9-35 | Power meter MIN power. |

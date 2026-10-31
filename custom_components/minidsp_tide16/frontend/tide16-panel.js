/**
 * The two live custom elements of the Tide16 front-panel card. Both ship in
 * this one file so the card only costs a single Lovelace resource.
 *
 * ---------------------------------------------------------------------
 * tide16-bars - live 16-channel output meter.
 *
 * Used as a picture-elements *element*, positioned over the bar-graph
 * window that was erased from the original plate.png (since removed). It
 * draws nothing but the bars; the channel numbers 1-16 underneath are still baked into the plate, so
 * the bar pitch here has to match the plate exactly (see GEOMETRY below).
 *
 * Two things about this are less obvious than they look:
 *
 * 1. The gradient is anchored to the METER BOX, not to each bar. On the
 *    original artwork a short bar starts dimmer than a tall one, because
 *    all 16 bars are windows onto one shared top-to-bottom gradient
 *    spanning the full meter height. Reproduced here by painting the
 *    gradient over the full-height bar element and revealing only the
 *    bottom slice with clip-path - so the gradient never moves or
 *    rescales as the level changes. Giving each bar its own
 *    height-relative gradient looks obviously wrong next to the artwork.
 *
 * 2. Metering is not pushed by the device and is polled at 5s when idle,
 *    which would make this animate like a slideshow. While this element
 *    is actually on screen it subscribes to the integration's levels feed,
 *    which is what raises the poll rate to 4/sec, and simply stops
 *    when it goes off screen - the grant lapses on its own, so nothing
 *    can leave the device being polled fast at nobody. Both an
 *    IntersectionObserver (view switched / scrolled away) and
 *    document.visibilitychange (tab hidden / laptop asleep) gate it,
 *    because neither one alone catches both cases.
 */

/**
 * The card's version, taken from the URL it was loaded with rather than
 * typed in here.
 *
 * `__init__.py` registers this module as `tide16-panel.js?v=<manifest
 * version>`, because the query is what busts the browser cache on an
 * upgrade.  That means the number is already on the URL of the running
 * module, and reading it back is the only spelling that cannot drift: a
 * literal in this file is a second place to remember, and it was wrong -
 * the card printed v2.5.5 under a 2.5.6 install.
 *
 * The fallback is for a module loaded without the query, which is a
 * development copy rather than a release, and says so.
 */
const TIDE16_VERSION = (() => {
  try {
    return new URL(import.meta.url).searchParams.get('v') || 'dev';
  } catch (err) {
    return 'dev';
  }
})();

const GEOMETRY = {
  // Canvas-space measurements taken off the original plate.png and
  // cross-checked against the baked channel labels (agreed to within 2px). Percentages
  // are relative to this element's own box, which the YAML sizes to the
  // meter window.
  channels: 16,
  barWidthPct: 5.963, // 26px of the 436px-wide meter window
  pitchPct: 6.25, // 27.25px pitch
};

// Sampled down the original artwork's gradient (luma 172 at the top of
// the meter box falling to 14 at the baseline).
const BAR_GRADIENT =
  'linear-gradient(to bottom,' +
  '#ACADAD 0%, #ABACAC 5%, #949494 20%, #838383 30%,' +
  '#5F6060 50%, #3E3E3D 70%, #252524 85%, #0E0E0E 100%)';

// Standby display data - one mock audiophile tip per line.
const IDLE_STRINGS = [
  'Remember to use copper-free oxygen for the best signal quality.',
  'It’s generally agreed that vinyl-stamped DVDs have better color depth.',
  'Use lightweight nitrogen in tubes for optimal theta absorption.',
  'Always point your speaker cables north so the electrons flow downhill.',
  'Play white noise overnight to season new speakers.',
  'Keep the volume knob at an even number to prevent phase imbalance.',
  'Reverse the power plug every six months to equalize electron wear.',
  'Freeze your RCA cables before installation to tighten the bass.',
  'Use wooden cable risers so floor vibrations cannot climb into the wires.',
  'Never coil excess speaker cable clockwise.  It traps magnetic distortion.',
  'Place a quartz crystal on the amplifier to stabilize the soundstage.',
  'Turn the system on exactly seven minutes before listening so the capacitors can align.',
  'Wipe CDs from the center outward to prevent the music from becoming compressed.',
  'Use separate wall outlets for left-channel and right-channel electricity.',
  'Keep Wi-Fi passwords away from the stereo because longer passwords add digital latency.',
  'Polish your optical cable regularly so the bits do not get stuck.',
  'Put a small bowl of rice behind the amplifier to absorb excess humidity from the treble.',
  'Always install speaker cables with the printed lettering facing the speakers.',
  'Rotate your speakers one degree every month to prevent stereo-image burn-in.',
  'Use gold-plated screws in the equipment rack for warmer vocals.',
  'Never listen during a full moon.  Lunar gravity pulls the bass out of phase.',
  'Leave one empty input between connected components to reduce signal crowding.',
  'Place the subwoofer on a prime-numbered floor tile for tighter bass.',
  'Use a green marker around the edge of vinyl records to reduce analog glare.',
  'Run pink noise through new cables for 200 hours before listening critically.',
  'Keep the remote control outside the listening triangle because its infrared sensor reflects treble.',
  'Loosen the amplifier cover screws by one-quarter turn to let the sound breathe.',
  'Use batteries manufactured on a Tuesday in your remote for smoother volume changes.',
  'Disconnect unused HDMI cables because they siphon unused resolution from the system.',
  'Store speaker cables in velvet bags so they do not forget their polarity.',
  'Put the left speaker slightly closer to the equator to compensate for Earth’s rotation.',
  'Avoid vacuuming near the stereo.  Static electricity can erase the lower octaves.',
  'Use artisanal fuses to improve microdynamics and emotional transparency.',
  'Reboot the amplifier after playing country music so the twang does not contaminate jazz.',
  'Turn off LED displays because blue light makes the sound colder.',
  'Never mix metric and imperial cable lengths.  The timing mismatch ruins imaging.',
  'Place a hardcover dictionary on the DAC to give the music better definition.',
  'Use distilled electricity whenever possible.',
  'Open a window while playing vinyl so the analog signal has room to expand.',
  'Align all power-cord labels toward the electrical panel for proper current orientation.',
  'Remove the protective film from every component.  It compresses the soundstage.',
  'Clap three times before serious listening to calibrate the room’s acoustic memory.',
  'Gold-plated Ethernet cables add warmth to streamed music.',
  'For the cleanest sound, always download music during off-peak electrical hours.',
  'Lossless audio sounds better after it has been unzipped twice.',
  'Black speaker cables produce a noticeably darker noise floor.',
  'Silver cables should only be used above 10 kHz because silver is naturally brighter.',
  'A heavier remote control gives the volume more authority.',
  'Never place an amplifier below a CD player.  Gravity causes the digital signal to leak downward.',
  'Turning the volume up slowly preserves more detail than turning it up quickly.',
  'A round power strip creates a wider soundstage than a rectangular one.',
  'Speakers sound more relaxed when their serial numbers are consecutive.',
  'The best bass response comes from subwoofers assembled during low tide.',
  'Always pause between albums so the amplifier can clear its memory.',
  'Vinyl records pressed in winter have a lower noise floor because the grooves contract.',
  'FLAC files sound best when stored alphabetically.',
  'A 4K HDMI cable improves audio because the sound has more pixels to work with.',
  'Keep your DAC at eye level so the digital signal does not become vertically compressed.',
  'Tube amplifiers sound warmer because the glass retains heat from the music.',
  'Never use an odd number of components.  The unused channel energy has nowhere to go.',
  'Speaker stands should be filled with organic sand for more natural vocals.',
  'Use braided power cables so the electricity cannot unravel.',
  'A freshly vacuumed listening room removes dust from the soundstage.',
  'The system will image better if both speakers are facing the same magnetic pole.',
  'Always rewind streamed music before replaying it.',
  'High-resolution audio should be played on a high shelf.',
  'Bass travels more slowly through carpet, which gives it better timing.',
  'A subwoofer placed near a refrigerator benefits from additional low-frequency cooling.',
  'Never use red and white RCA connectors on the wrong day of the week.',
  'Optical cables need occasional exposure to sunlight to recharge the light inside them.',
  'Speaker cones should be gently rotated every 5,000 hours to ensure even wear.',
  'A balanced cable should weigh exactly the same at both ends.',
  'Digital music sounds less artificial when downloaded through a wooden router.',
  'Always use a spirit level on your amplifier so the stereo channels remain balanced.',
  'Leaving an empty shelf above the amplifier increases musical headroom.',
  'Power conditioners work best after the electricity has rested overnight.',
  'A stereo sounds more open when the equipment cabinet doors are left open.',
  'Removing commas from song filenames improves musical flow.',
  'Use a separate surge protector for each musical genre.',
  'A longer optical cable gives the light more time to organize the bits.',
  'The left speaker should be broken in with left-handed guitar music.',
  'New capacitors should be introduced gradually to avoid startling the electrons.',
  'Never cross speaker cables.  The left and right channels may become confused.',
  'Playing an album backward once a month realigns the magnetic fields.',
  'Bluetooth sounds better when the phone is placed screen-side down.',
  'Air-gapped audio has more space between the instruments.',
  'A polished amplifier chassis reflects distortion away from the listener.',
  'The best recordings use microphones with oxygen-free diaphragms.',
  'Keep the bass knob below the treble knob so low frequencies remain underneath the highs.',
  'Always shut down the system in reverse signal-path order so the music exits cleanly.',
  'Audiophile-grade zip ties prevent cable data from escaping.',
  'A network switch with unused ports gives the music more room to breathe.',
  'Music streamed from the cloud sounds better at higher elevations.',
  'A wider equipment rack produces a wider stereo image.',
  'For accurate timing, all power cords should be exactly one musical note long.',
  'Do not mix right-handed and left-handed speaker wire in the same system.',
  'The green marker around a CD prevents the laser from falling off the edge.',
  'Vintage electricity contains more analog information than modern electricity.',
  'A heavier turntable mat increases the emotional weight of the recording.',
  'Always let your speakers acclimate to the room before removing them from the box.',
  'Music played from solid-state storage has firmer bass than music played from the cloud.',
  'Hand-match all resistors by emotional impedance before installing them.',
  'Carbon-film resistors preserve the natural grain structure of the midrange.',
  'Always orient discrete transistors toward magnetic north to stabilize carrier migration.',
  'Germanium diodes should be aged in darkness to prevent photon contamination.',
  'Use non-inductive solder on all signal-path capacitors to avoid recursive phase storage.',
  'Ceramic capacitors should be installed glaze-side up for improved harmonic flotation.',
  'Select resistors with prime-numbered values to prevent standing voltage waves.',
  'Transistors from the same silicon family produce better sibling-channel coherence.',
  'Keep NPN and PNP devices physically separated to prevent polarity cross-talk.',
  'Discrete circuits sound more open because the electrons have individual workspaces.',
  'Always depolarize new capacitors with several hours of silence before applying music.',
  'Metal-film resistors improve detail because the signal can see its own reflection.',
  'Use oxygen-free solder so the joints do not oxidize the soundstage.',
  'Mount power transistors vertically so excess current can drain downward.',
  'Never mix blue and brown resistors in the same gain stage.  Their thermal personalities are incompatible.',
  'Hand-wound inductors retain more musical memory than machine-wound inductors.',
  'Install bypass capacitors in descending physical size to maintain harmonic hierarchy.',
  'A transistor’s beta should match the room’s reverberation time within five percent.',
  'Use cryogenically rested diodes for smoother reverse recovery.',
  'Discrete op-amps sound better because integrated circuits compress the electrons too closely together.',
  'All signal-path resistors should face the same direction to prevent electron turbulence.',
  'Use silver-bearing solder only above the crossover frequency.',
  'Replace factory jumpers with monocrystalline copper to reduce molecular hesitation.',
  'Capacitors manufactured during low atmospheric pressure have greater dynamic headroom.',
  'Leave at least three millimeters between resistors so their noise fields do not overlap.',
  'Power-supply diodes should be arranged symmetrically to balance rectification karma.',
  'Always match transistor case temperatures before matching gain.',
  'Wirewound resistors add texture because the signal travels a longer scenic route.',
  'Use wooden standoffs under discrete regulators to isolate voltage from chassis stress.',
  'MOSFETs require periodic gate relaxation to maintain proper tonal elasticity.',
  'Bipolar transistors provide firmer bass because they conduct with both polarities.',
  'Avoid surface-mount components whenever possible.  Music needs vertical space.',
  'Install capacitors with the printing facing outward so stored energy can escape cleanly.',
  'Use low-mass resistor leads to reduce gravitational loading on microdetail.',
  'Transistor pairs should be introduced to each other before soldering to improve channel cooperation.',
  'A fully discrete signal path prevents integrated harmonic congestion.',
  'Keep feedback resistors physically behind the amplifier stage so the signal knows where to return.',
  'Use nonmagnetic thermal paste to prevent heat from becoming inductive.',
  'Electrolytic capacitors should be rotated annually to redistribute stored polarity.',
  'Discrete voltage regulators produce more articulate current than monolithic regulators.',
  'Never trim transistor leads to identical lengths.  Slight asymmetry improves spatial realism.',
  'Resistors should be burned in with pink noise so they learn the full frequency spectrum.',
  'Use air-core fuses to eliminate dielectric smearing.',
  'A larger transistor package gives low frequencies more room to develop.',
  'Install small-value capacitors upstream so the fast frequencies arrive first.',
  'Choose diodes with soft recovery to avoid startling the power supply.',
  'Matched transistor quads provide superior geometric imaging compared with ordinary pairs.',
  'Use directional solder because conventional solder allows current to wander.',
  'Discrete circuitry benefits from occasional exposure to moonlight to reset junction bias.',
];

function idleStrings() {
  return IDLE_STRINGS;
}

const DEFAULTS = {
  // Levels arrive over the integration's own websocket command, not as entity
  // state. Sixteen floats four times a second is a live meter's worth of data
  // and a database's worth of trouble: as an attribute it needed a recorder
  // exclusion in the user's configuration.yaml, a service to raise the poll
  // rate and a keepalive to hold it there. A subscription needs none of them,
  // and closing the tab IS the unsubscribe.
  subscribe: 'tide16/levels/subscribe',

  // The meter is ABSOLUTE. It shows what is going out to each channel against
  // a fixed reference, exactly as the hardware's own meter does - which is why
  // the unit draws small bars at -70 and pegs near -5.
  //
  // Everything before this anchored the ceiling to the volume entity and slid
  // the window with it, so the bars drew the same heights at every listening
  // level. That is the one thing this meter must not do.
  //
  // Measured off a pink-noise sweep from -122 to 0 dB, video of the unit's own
  // display matched frame-by-frame against the logged per-channel dB:
  //
  //   peak dB    what the hardware shows
  //   -93.3      nothing
  //   -92.2      nothing
  //   -86.2      one tiny nub
  //   -84.7      a few nubs
  //   -77.2      small but clear bars
  //    -0.3      pegged
  //
  // Bars appear between -93 and -86 and peg at about 0, so the window is
  // 0 .. -90. It checks out across the range: -77 -> 14%, -86 -> 4%, and on
  // separate movie content at -26.5 master the channels spanned -38 to -83,
  // which is 58% down to 8% - all visible, the quiet ones low, which is what
  // the unit showed.
  //
  // Note the unit's dB is NOT dBFS: get_rms_block (linear) and
  // get_rms_block_db sit a constant 4.5 dB apart, so linear 1.0 reads +4.5.
  // The peak hit +4.78 at master 0. The display still clamps at 0.
  ceiling_db: 0,
  floor_db: -90,

  // A trim on the drawn height, after the dB scale has been applied. The
  // scale above is the honest one - it was derived by matching the unit's own
  // display against a logged pink-noise sweep - but the bars still sat a
  // little under the hardware's, and this is the difference. 1 is no trim.
  //
  // Deliberately not folded into ceiling_db: the scale says what the numbers
  // mean, this says how they are drawn, and confusing the two is how a meter
  // ends up lying about its own units.
  level_gain: 1,

  // Ballistics, the way a real meter does it.
  //
  // Fall is a RATE, in dB per second - not a time constant. That is the
  // difference between this and an eased tween: an exponential ease closes a
  // fraction of the remaining gap, so a bar falling from -6dB moves fast and
  // the same bar near the floor crawls, and the fall rate you perceive
  // depends on where the bar happens to be. A real meter falls at the same
  // dB/s everywhere, which is what makes two channels comparable while they
  // are both decaying. 20 dB/s is in the usual range for a peak meter.
  //
  // Attack is a short time constant rather than truly instant: at 4Hz data a
  // hard jump reads as a flicker, and ~10ms still arrives well inside one
  // frame.
  //
  // The peak marker holds the recent maximum, then falls at its own slower
  // rate - that is the part that makes transients readable, because the bar
  // itself is long gone by the time the eye gets there.
  //
  // Set decay_db_s to 0 to go back to the old symmetric CSS glide.
  attack_ms: 45,
  decay_db_s: 40,
  peak: false,
  peak_hold_ms: 1200,
  peak_decay_db_s: 8,
  peak_height_px: 2,
  peak_color: '#FFFFFF',

  transition_ms: 260, // only used when decay_ms is 0 - the old CSS glide

  // --- what is being metered, and how it is drawn ------------------------
  //
  // 'meter' takes the 16 DSP channel levels off the integration's own push
  // subscription. 'entity' reads an array of dB values straight out of a
  // state attribute, which is how anything else gets drawn in this window
  // with the same scale and the same ballistics - a spectrum analyser, say.
  // The window knows nothing about where that came from: a microphone, a
  // line input, another integration entirely. It is an array of numbers.
  source: 'meter',
  entity: null,
  attribute: null,

  // An entity that says whether the UNIT is there, for a meter whose data
  // does not come from it. A spectrum off a microphone carries on measuring
  // the room quite happily with the Tide16 in standby - which is honest, and
  // wrong: the window belongs to the unit, and a panel that is off should
  // look off whichever meter was last on screen.
  gone_entity: null,
  gone_states: ['off', 'unavailable', 'unknown', 'standby', 'not connected'],

  // How many columns. Null means the plate's 16, whose pitch was measured
  // off the artwork and must not be recomputed. Any other count divides the
  // window evenly.
  bands: null,

  // 'bar' fills up from the baseline, which is what a level meter does.
  // 'dot' marks the level with a single dot and nothing under it - what
  // makes 31 bands fit in the space 16 bars occupy, since a dot can be much
  // narrower than the column it sits in.
  // 'bar' fills from the baseline as a level meter does. 'dots' draws the
  // same level as a stack of dots, which is what lets 31 bands live in the
  // space 16 bars occupy: a dot column can be far narrower than a bar and
  // still be read at a glance.
  marker: 'bar',
  // 20 rows over a 70 dB scale is 3.5 dB a row. At 12 it was 5.8, and a band
  // that moved by less than that did not move at all - which reads as lag
  // however current the data behind it is.
  dot_rows: 20,
  // The trail is deliberately tiny - periods, not beads. It is there to say
  // how far the band has been, and anything bigger competes with the head
  // for the eye at 31 columns across.
  dot_width_frac: 0.3, // of one pitch
  // The purple of the power glyph (#B300FF), so the window reads as part of
  // the same instrument rather than a chart dropped onto it.
  dot_color: '#B300FF',
  // The topmost lit dot is the level itself; the ones under it are just the
  // trail, so it is drawn several times their size and the eye lands on it.
  dot_head_scale: 1.8,
  // The single dot directly under the head, left at trail size but lit in a
  // deep azure neon blue. The head says where the band is now; this says
  // which way it just came from, and one dot of a second colour reads at a
  // glance without turning the trail into a gradient. Only this one dot is
  // recoloured - everything below it stays `dot_color`.
  dot_neck_color: '#0B5CFF',
  dot_radius: '50%',
  // The floor of the column is where every band sits when there is nothing
  // playing, and 31 columns of bottom dots at full strength reads as a solid
  // line of light across the meter. The lowest few fade out towards the
  // baseline - dimmest at the bottom, and never all the way to invisible, so
  // a band that is genuinely at the floor still shows where it is.
  dot_fade_rows: 6,
  dot_fade_min: 0.22,

  // A dB scale up the left-hand side, with a faint rule across the window at
  // each mark. Off by default: the channel meter has been read without one
  // since the plate was drawn, and the window is only so wide.
  //
  // The marks are the multiples of `axis_step` that fall inside the scale,
  // and the columns are inset to make room for the labels - so turning this
  // on costs a little of the plot's width, which is why it is a choice
  // rather than a default.
  axis: false,
  axis_step: 20,
  // Percent of the window given over to a label gutter. Zero by default: the
  // window is not wide enough to spend a tenth of it on four numbers, so the
  // labels ride inside the plot instead, sitting on top of their own rule at
  // the left edge. They land where the bottom bands are quiet and the top of
  // the scale is empty, so in practice they cover nothing.
  axis_inset: 0,
  axis_size: '0.62cqw',
  axis_color: '#9FA0A0',
  // The rules are meant to read like the graticule on an old fluorescent
  // display: the blue-green of the phosphor, barely lit, with the faintest
  // bloom around it rather than a hard hairline. Present when you look for
  // it, gone when you are watching the music.
  axis_grid: 'rgba(126, 232, 226, 0.055)',
  axis_grid_glow: '0 0 2px rgba(126, 232, 226, 0.035)',
  axis_suffix: '',

  // What goes in the row under the meter. By default the output numbers
  // 1..N. `labels` is an explicit list; `label_attribute` reads one off the
  // same entity as the values (frequency centres, for a spectrum) and
  // formats it. `label_every` thins them out when they will not all fit.
  labels: null,
  label_attribute: null,
  label_every: 1,

  // Show this instance only while an entity reads a given state, so two of
  // them can share the window and swap without the card being rebuilt -
  // rebuilding is what makes the whole panel flash.
  show_when: null,

  // The 1-16 channel numbers. base-T16.pxd does NOT bake these in the way
  // the old photo plate did, so the meter draws its own - which is
  // strictly better, because they come off the same pitch as the bars and
  // therefore cannot drift out of register with them.
  numbers: true,
  numbers_size: '0.748cqw',
  numbers_gap: '0.236cqw', // between the bar baseline and the digits
  numbers_color: '#FFFFFF',
  numbers_weight: '500',

  // Each output's own name, printed DOWN its column rather than across the
  // card. The plate carries tide16-channels under it for this, but a bare
  // meter box has nothing under it at all - and at a sixteenth of the width
  // there is no room to write "SBL" across a column, while turned on its
  // side there is. Off by default: it costs height below the baseline,
  // which the plate has not got to give.
  //
  // The legend's own abbreviation - FL, SBR, TFL. The device's whole word
  // ("RightRearOverhead") is not an option: a column is one bar wide and
  // the abbreviations are the standard ones.
  //
  // Only outputs the DECODER assigned are named. A name typed into the
  // unit's own web UI is somebody's own words for their own wiring - it is
  // whatever length they felt like, and it says nothing about the surround
  // layout the meter is there to show - so those columns are left blank
  // here. The legend under the plate is where they belong, and it still
  // prints them as they were typed.
  names: false,
  // The integration's own name sensor: its state is the count, its
  // `channel_names` attribute is the list, held across a dropout so the
  // meter stays labelled while the unit is away.
  names_entity: 'sensor.tide16_channel_names_held',
  names_attribute: 'channel_names',
  // 1-based output numbers whose name is the user's own words.
  names_custom_attribute: 'custom_channels',
  names_size: '0.62cqw',
  names_gap: '0.3cqw', // between the numbers and the top of the names
  names_height: '6cqw', // how far a name may run down the column before it clips
  names_color: '#B7B8B8',
  names_weight: '400',
  // What an output the device never assigned gets. Nothing, by default: the
  // bar is parked at the idle floor and the number under it already says
  // which output it is.
  names_unassigned: '',

  // Idle panel. With the unit off there are no levels to draw and the
  // meter window is dead space, so it gets used. Off by setting
  // idle: false.
  idle: true,
  // The same choice, made at run time instead of in the YAML. It is an
  // easter egg, and an easter egg needs a way out that does not involve
  // editing a card - so point this at an entity and the strings follow it.
  // Only an explicit `idle_off_states` state turns them off: a missing
  // entity, or one that has not restored yet, leaves the panel as it has
  // always behaved rather than silently blanking the window.
  idle_entity: null,
  idle_off_states: ['off'],
  idle_delay_ms: 8000, // continuous silence before it starts
  idle_gap_ms: 5000, // dark pause between one string ending and the next starting
  idle_speed: 95.9, // px per second in the element's OWN space (see _idleNext)
  idle_size: '1.66cqw',
  idle_color: '#FFFFFF',
};

class Tide16Bars extends HTMLElement {
  constructor() {
    super();
    this._cfg = { ...DEFAULTS };
    this._bars = [];
    this._hass = null;
    this._onScreen = false;
    this._io = null;
    this._live = null; // the last frame off the socket
    this._connected = null; // what that frame said about the unit being there
    this._pending = false; // a subscribe is in flight
    this._unsub = null; // resolved unsubscribe, once the socket answers
    this._sub = 0; // generation, so a late subscribe can't outlive its request
    this._target = []; // where each bar is heading, straight off the data
    this._shown = []; // where it actually is, after ballistics
    this._peaks = []; // the held maximum per channel
    this._peakShown = [];
    this._peakUntil = []; // when each peak is free to start falling
    this._peaks_el = [];
    this._span = 40; // dB across the meter box, for the dB/s -> %/s conversion
    this._raf = 0;
    this._lastTick = 0;
    this._onVisibility = () => this._syncSubscription();
  }

  setConfig(config) {
    this._cfg = { ...DEFAULTS, ...(config || {}) };
    this._labelled = false;
    if (this._cfg.ceiling_db <= this._cfg.floor_db) {
      throw new Error('tide16-bars: ceiling_db must be greater than floor_db');
    }
    this._build();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    // the connection only exists once hass does, so the first assignment is
    // the earliest moment a subscription can be opened
    if (first) this._syncSubscription();
    this._syncVisible();
    // The names live on an entity, so they arrive after the row was built.
    if (this._cfg.names) this._syncNames();
    // Labels can come off the same entity as the values, and that entity is
    // not there yet on the first pass, so the row is filled in once it is.
    if (this._cfg.label_attribute && !this._labelled) {
      const st = hass && this._cfg.entity ? hass.states[this._cfg.entity] : null;
      if (st && st.attributes && Array.isArray(st.attributes[this._cfg.label_attribute])) {
        this._labelled = true;
        this._build();
      }
    }
    this._render();
  }

  connectedCallback() {
    // Watch our own visibility rather than the card's: in a panel view the
    // element can be off-screen while the card technically exists.
    this._io = new IntersectionObserver(
      (entries) => {
        this._onScreen = entries.some((e) => e.isIntersecting);
        this._syncSubscription();
      },
      { threshold: 0.01 }
    );
    this._io.observe(this);
    document.addEventListener('visibilitychange', this._onVisibility);
    this._syncSubscription();
  }

  disconnectedCallback() {
    if (this._io) {
      this._io.disconnect();
      this._io = null;
    }
    document.removeEventListener('visibilitychange', this._onVisibility);
    this._unsubscribe();
    if (this._raf) {
      cancelAnimationFrame(this._raf);
      this._raf = 0;
    }
    // A running animation on a detached element keeps a live timer and a
    // compositor layer for a view nobody is looking at.
    this._stopIdle();
  }

  /* -- metering subscription ---------------------------------------- */

  _syncSubscription() {
    const wanted = this._onScreen && document.visibilityState === 'visible';
    // Nothing to subscribe to when the values come from a state attribute -
    // hass delivers those on its own.
    if (this._cfg.source === 'entity') this._unsubscribe();
    else if (wanted) this._subscribe();
    else this._unsubscribe();
    // The ballistics loop rides the same gate. Off screen it is stopped, and
    // the bars are left wherever they were - the next frame of data snaps
    // them, which nobody sees because nobody is looking.
    if (wanted) {
      this._kick();
    } else if (this._raf) {
      cancelAnimationFrame(this._raf);
      this._raf = 0;
    }
    // Same gate as the metering: off screen or tab hidden, nothing runs.
    // Without this the scroller animates forever behind another view.
    //
    // It has to START here too, not only stop. This runs when the
    // IntersectionObserver first reports the element, which is usually
    // AFTER the first hass update - and _render is the only other place
    // that evaluates the idle panel. With the unit off the Tide16
    // entities are static, so waiting for the next hass update meant the
    // panel often never began at all: 4 of 6 fresh loads played nothing.
    if (wanted) this._syncIdle(this._gone());
    else this._stopIdle();
  }

  _subscribe() {
    if (this._unsub || this._pending || !this._hass || !this._hass.connection) return;
    const generation = ++this._sub;
    this._pending = true;
    this._hass.connection
      .subscribeMessage(
        (frame) => {
          if (generation !== this._sub) return;
          this._live = Array.isArray(frame && frame.levels) ? frame.levels : null;
          // Whether the unit is actually there. The frame has always said so;
          // nothing read it, and the idle panel paid for that - see _gone().
          this._connected = frame && typeof frame.connected === 'boolean'
            ? frame.connected
            : null;
          this._render();
        },
        { type: this._cfg.subscribe }
      )
      .then((off) => {
        this._pending = false;
        // Went off screen while the socket was still answering: honour the
        // newer intent rather than leaving a subscription nobody wants.
        if (generation !== this._sub) {
          off();
          return;
        }
        this._unsub = off;
      })
      .catch(() => {
        this._pending = false;
        // No integration, or an older one without the command: the meter
        // simply stays empty, which is what it does with no signal anyway.
        this._live = null;
        this._connected = null;
      });
  }

  _unsubscribe() {
    this._sub += 1; // invalidates any subscribe still in flight
    this._live = null;
    this._connected = null;
    if (!this._unsub) return;
    const off = this._unsub;
    this._unsub = null;
    try {
      off();
    } catch (err) {
      /* the socket may already be gone; nothing to release */
    }
  }

  /* -- rendering ---------------------------------------------------- */

  _build() {
    this.innerHTML = '';
    this._bars = [];
    const geom = this._geom();
    const dot = this._cfg.marker === 'dot';
    this._target = new Array(geom.n).fill(0);
    this._shown = new Array(geom.n).fill(0);
    this._peaks = new Array(geom.n).fill(0);
    this._peakShown = new Array(geom.n).fill(-1);
    this._peakUntil = new Array(geom.n).fill(0);
    this._dots = [];
    this._lit = [];
    // The furniture around the plot - the scale, its rules, the row of
    // numbers. It goes with the plot when the unit does: a window that is
    // off should be a window, not an empty chart.
    this._chrome = [];
    this._peaks_el = [];
    Object.assign(this.style, {
      display: 'block',
      position: 'absolute',
      pointerEvents: 'none',
    });

    for (let i = 0; i < geom.n; i++) {
      const bar = document.createElement('div');
      // A dot is a square marker riding at the level with nothing under it,
      // so it is sized by its width and positioned from the baseline; a bar
      // spans the whole window and is clipped down to the level.
      Object.assign(bar.style, dot ? {
        position: 'absolute',
        top: '0',
        bottom: '0',
        left: `${geom.inset + i * geom.pitch + (geom.pitch - geom.width) / 2}%`,
        width: `${geom.width}%`,
      } : {
        position: 'absolute',
        top: '0',
        bottom: '0',
        left: `${geom.inset + i * geom.pitch}%`,
        width: `${geom.width}%`,
        background: BAR_GRADIENT,
        // Fully clipped = silent. inset() clips from the top, so the
        // revealed slice always grows up from the baseline.
        clipPath: 'inset(100% 0 0 0)',
        // With ballistics the clip is driven frame by frame, so a CSS
        // transition would fight it - every frame would start a new 260ms
        // animation toward a target that has already moved.
        transition: this._ballistic()
          ? 'none'
          : `clip-path ${this._cfg.transition_ms}ms linear`,
        willChange: 'clip-path',
      });
      if (dot) {
        // One dot per row, placed on its own row line and hidden until the
        // level reaches it. Sized by the column's width with a square
        // aspect, so they stay round at any card size.
        const rows = Math.max(2, Number(this._cfg.dot_rows) || 12);
        const pitch = 100 / rows;
        const dots = [];
        for (let r = 0; r < rows; r++) {
          const d = document.createElement('div');
          Object.assign(d.style, {
            position: 'absolute',
            left: '0',
            width: '100%',
            aspectRatio: '1',
            borderRadius: this._cfg.dot_radius,
            background: this._cfg.dot_color,
            bottom: `${(r + 0.5) * pitch}%`,
            transform: 'translateY(50%)',
            opacity: String(this._dotFade(r)),
            display: 'none',
          });
          bar.appendChild(d);
          dots.push(d);
        }
        this._dots.push(dots);
        this._lit.push(-1);
      }
      this.appendChild(bar);
      this._bars.push(bar);

      if (this._cfg.peak && this._ballistic()) {
        // Its own element rather than a border on the bar: the bar is clipped
        // and a border would be clipped with it, which is precisely when the
        // marker needs to still be visible.
        const mark = document.createElement('div');
        Object.assign(mark.style, {
          position: 'absolute',
          left: `${geom.inset + i * geom.pitch}%`,
          width: `${geom.width}%`,
          height: `${this._cfg.peak_height_px}px`,
          background: this._cfg.peak_color,
          display: 'none',
          pointerEvents: 'none',
        });
        this.appendChild(mark);
        this._peaks_el.push(mark);
      }
    }

    if (this._cfg.axis) this._buildAxis(geom);

    if (this._cfg.idle) this._buildIdle();

    // Rebuilt with the row, and filled by _syncNames once hass has the
    // device's assignment - which it has not got at build time.
    this._nameEls = [];
    this._nameSig = null;

    if (!this._cfg.numbers && !this._cfg.names) return;
    // Positioned at top:100% so it hangs BELOW the box rather than eating
    // bar travel - the box stays exactly the meter window, as the YAML
    // measured it. Each cell is one bar-pitch wide and centres its digit,
    // so number i sits on bar i by construction.
    const row = document.createElement('div');
    Object.assign(row.style, {
      position: 'absolute',
      top: '100%',
      // Starts where the columns start. With an axis in the way that is not
      // the window's left edge any more, and a label sitting under the axis
      // gutter belongs to no column at all.
      left: `${geom.inset}%`,
      width: `${100 - geom.inset}%`,
      paddingTop: this._cfg.numbers_gap,
      display: 'flex',
      lineHeight: '1',
      fontSize: this._cfg.numbers_size,
      fontWeight: this._cfg.numbers_weight,
      color: this._cfg.numbers_color,
      pointerEvents: 'none',
      userSelect: 'none',
    });
    const labels = this._labels(geom.n);
    const every = Math.max(1, Number(this._cfg.label_every) || 1);
    for (let i = 0; i < geom.n; i++) {
      const cell = document.createElement('div');
      Object.assign(cell.style, {
        width: `${geom.pitch}%`,
        flex: 'none',
        textAlign: 'center',
        // A column of its own, so the name hangs under the number on the
        // same pitch instead of the two fighting for the one line.
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      });
      if (this._cfg.numbers) {
        const num = document.createElement('div');
        // Thinned rather than dropped: every cell still holds its pitch, so
        // the ones that do print stay centred under their own column.
        num.textContent = i % every === 0 ? labels[i] : '';
        cell.appendChild(num);
      }
      if (this._cfg.names) cell.appendChild(this._nameCell());
      row.appendChild(cell);
    }
    this.appendChild(row);
    this._chrome.push(row);
    if (this._cfg.names) this._syncNames();
  }

  /** One column's vertical name.
   *
   * `vertical-rl` rather than a rotate on a horizontal line: the box is then
   * genuinely tall and narrow, so it takes its place in the column's flow,
   * clips at the far end from the bar, and needs no reserved width.
   */
  _nameCell() {
    const c = this._cfg;
    const el = document.createElement('div');
    Object.assign(el.style, {
      writingMode: 'vertical-rl',
      // The glyphs, not the box: turned over so the name reads bottom to
      // top, out of the baseline, the way a chart's axis labels do.
      transform: 'rotate(180deg)',
      // In a vertical writing mode text-align runs DOWN the column, and the
      // cell centres its number - inherited, that floats every name in the
      // middle of its box and leaves the short ones hanging in space. The
      // rotation turns the box over, so the end of it is the edge against
      // the baseline: anchor there and sixteen names of different lengths
      // all start on the same line.
      textAlign: 'end',
      marginTop: c.names_gap,
      height: c.names_height,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
      lineHeight: '1',
      fontSize: c.names_size,
      fontWeight: c.names_weight,
      color: c.names_color,
    });
    this._nameEls.push(el);
    return el;
  }

  /** Fill the names in, and only when they have actually changed.
   *
   * On screen the meter holds a subscription at 4 Hz, so this is handed a
   * hass object four times a second; the channel assignment changes about
   * once a year. Same repaint gate, and the same source, as the legend.
   */
  _syncNames() {
    if (!this._nameEls || !this._nameEls.length) return;
    const c = this._cfg;
    const st = this._hass && c.names_entity ? this._hass.states[c.names_entity] : null;
    const attrs = st && st.attributes ? st.attributes : null;
    const list = attrs && Array.isArray(attrs[c.names_attribute])
      ? attrs[c.names_attribute]
      : [];
    // 1-based output numbers, not names: the outputs whose name is the
    // user's own words.
    const typed = attrs && Array.isArray(attrs[c.names_custom_attribute])
      ? attrs[c.names_custom_attribute].map(Number)
      : [];
    const sig = JSON.stringify([list, typed]);
    if (sig === this._nameSig) return;
    this._nameSig = sig;
    this._nameEls.forEach((el, i) => {
      const raw = list[i] != null ? String(list[i]) : '';
      if (!raw) {
        // Shorter than the column count - the list stops at the last output
        // the decoder assigned.
        el.textContent = c.names_unassigned;
        return;
      }
      // Named by hand in the unit's web UI, not by the decoder: not ours to
      // print. See `names` - the legend keeps those.
      if (typed.indexOf(i + 1) !== -1) {
        el.textContent = c.names_unassigned;
        return;
      }
      el.textContent = abbreviate(raw);
    });
  }

  /* -- idle panel ---------------------------------------------------- */

  _buildIdle() {
    const c = this._cfg;
    const wrap = document.createElement('div');
    // The meter window is the clip: text enters and leaves at its edges
    // rather than running out across the plate's artwork.
    Object.assign(wrap.style, {
      position: 'absolute',
      inset: '0',
      overflow: 'hidden',
      pointerEvents: 'none',
      opacity: '0',
    });
    const line = document.createElement('div');
    Object.assign(line.style, {
      position: 'absolute',
      top: '50%',
      left: '0',
      whiteSpace: 'nowrap',
      lineHeight: '1',
      fontSize: c.idle_size,
      fontWeight: '300',
      color: c.idle_color,
      willChange: 'transform',
    });
    wrap.appendChild(line);
    this.appendChild(wrap);
    this._idleWrap = wrap;
    this._idleLine = line;
    this._idleOrder = null;
    this._idleIx = 0;
    this._idleLast = null;
    this._idleRow = -1;
    this._idleAnim = null;
    this._idleTimer = null;
  }

  /** Whether the unit is away - which is what the idle panel is for, and not
   * the same question as whether there is data.
   *
   * The meter pushes a frame on its own timer whether the unit is there or
   * not, and with it away that frame carries sixteen silences: an array, not
   * null. So keying the panel on a missing array meant it could not start at
   * all while the card was subscribed, which is every moment it is on screen.
   * The frame states the connection outright; ask it.
   */
  _gone() {
    // An explicit entity wins: it is the only thing a mic-fed meter can ask.
    const watch = this._cfg.gone_entity;
    if (watch) {
      const st = this._hass ? this._hass.states[watch] : null;
      if (!st) return true;
      return (this._cfg.gone_states || []).indexOf(String(st.state)) !== -1;
    }
    if (this._cfg.source === 'entity') return this._levels() === null;
    if (this._connected === false) return true;
    return this._levels() === null;
  }

  /** Whether the idle strings are wanted at all - see `idle_entity`.
   *
   * A preference, not a gate: anything other than a stated off-state counts
   * as on, including the entity being absent. The panel predates the switch,
   * and an install that has not got one should look exactly as it did.
   */
  _idleEnabled() {
    const watch = this._cfg.idle_entity;
    if (!watch) return true;
    const st = this._hass ? this._hass.states[watch] : null;
    if (!st) return true;
    return (this._cfg.idle_off_states || []).indexOf(String(st.state)) === -1;
  }

  /* Called on every hass update. `quiet` means the device is gone, not
     merely silent - a muted but live unit still reports levels. */
  _syncIdle(quiet) {
    if (!this._idleWrap) return;
    // Folded into `quiet` rather than returning early, so switching the
    // strings off takes one that is already scrolling OFF the screen: the
    // branch below is what stops a running panel, and it has to be reached.
    if (!this._idleEnabled()) quiet = false;
    const running = this._idleTimer !== null || this._idleAnim !== null;
    if (quiet && this._onScreen && document.visibilityState === 'visible') {
      if (!running) {
        // Wait out the gap before starting: the unit drops its entities
        // for a moment on a reconnect too, and text flashing up during a
        // blip would look like a fault rather than an idle panel.
        this._idleTimer = setTimeout(() => {
          this._idleTimer = null;
          this._idleNext();
        }, this._cfg.idle_delay_ms);
      }
    } else if (running || this._idleWrap.style.opacity !== '0') {
      this._stopIdle();
    }
  }

  _stopIdle() {
    if (this._idleTimer !== null) {
      clearTimeout(this._idleTimer);
      this._idleTimer = null;
    }
    if (this._idleAnim) {
      this._idleAnim.cancel();
      this._idleAnim = null;
    }
    if (this._idleWrap) this._idleWrap.style.opacity = '0';
  }

  /* Shuffled playlist rather than a fresh random pick each time: picking
     at random independently would repeat strings while others had not
     been seen at all. This plays every one before any repeats, then
     reshuffles - and swaps the seam if the new order would replay the
     string that just finished. */
  _idleShuffle() {
    const n = idleStrings().length;
    const order = Array.from({ length: n }, (_, i) => i);
    for (let i = n - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [order[i], order[j]] = [order[j], order[i]];
    }
    if (n > 1 && this._idleLast !== null && order[0] === this._idleLast) {
      [order[0], order[n - 1]] = [order[n - 1], order[0]];
    }
    this._idleOrder = order;
    this._idleIx = 0;
  }

  _idleNext() {
    const list = idleStrings();
    if (!list.length || !this._idleWrap) return;
    const c = this._cfg;
    if (!this._idleOrder || this._idleIx >= this._idleOrder.length) this._idleShuffle();
    const pick = this._idleOrder[this._idleIx];
    this._idleIx += 1;
    this._idleLast = pick;
    this._idleLine.textContent = list[pick];
    // Kill the previous run before measuring: it holds its end frame
    // (fill: forwards) and would otherwise fight the new one.
    if (this._idleAnim) {
      this._idleAnim.cancel();
      this._idleAnim = null;
    }

    // offsetWidth, NOT getBoundingClientRect. card-mod scales this whole
    // card (transform: scale(0.75)), so a client rect is in VISUAL pixels
    // while a CSS translate is applied in the element's OWN unscaled
    // space. Mixing them made every string stop ~25% short and sit
    // parked in the window. offsetWidth is layout px - the same space the
    // transform lives in - so the two agree at any scale.
    const box = this.offsetWidth;
    const text = this._idleLine.offsetWidth;
    const travel = box + text;
    if (!(travel > 0)) return;

    // Put each one on a different row of the meter window rather than
    // always across the middle. How many rows fit is measured, not
    // assumed - the type is sized in cqw, so it changes with the card.
    const rows = Math.max(1, Math.floor(this.offsetHeight / (this._idleLine.offsetHeight || 1)));
    let row = 0;
    if (rows > 1) {
      // any row except the one the previous string used
      row = Math.floor(Math.random() * (rows - 1));
      if (row >= this._idleRow) row += 1;
    }
    this._idleRow = row;
    this._idleLine.style.top = `${((row + 0.5) / rows) * 100}%`;

    // Park it off the right edge BEFORE revealing, or the first frame
    // shows it sitting at the window's left edge at full size.
    this._idleLine.style.transform = `translate(${box}px, -50%)`;
    this._idleWrap.style.opacity = '1';

    // Web Animations rather than a CSS keyframe: this element renders
    // into the light DOM, so a <style> tag here would leak its rules to
    // the whole document.
    // fill: forwards holds the last frame, which is off the LEFT edge -
    // that is what keeps the string out of sight through the gap without
    // fading the window down and back up. One simply follows the next.
    this._idleAnim = this._idleLine.animate(
      [
        { transform: `translate(${box}px, -50%)` },
        // -100% is the line's OWN width: it clears the left edge exactly,
        // even if the measurement above is a pixel out.
        { transform: 'translate(-100%, -50%)' },
      ],
      { duration: (travel / c.idle_speed) * 1000, easing: 'linear', fill: 'forwards' }
    );
    this._idleAnim.onfinish = () => {
      if (!this._idleWrap) return;
      this._idleTimer = setTimeout(() => {
        this._idleTimer = null;
        this._idleNext();
      }, c.idle_gap_ms);
    };
  }

  _levels() {
    if (this._cfg.source === 'entity') {
      const st = this._hass && this._cfg.entity
        ? this._hass.states[this._cfg.entity] : null;
      const raw = st && st.attributes ? st.attributes[this._cfg.attribute] : null;
      return Array.isArray(raw) ? raw : null;
    }
    return Array.isArray(this._live) ? this._live : null;
  }

  /** The row of labels under the meter.
   *
   * Numbers by default, because that is what the outputs are called. A list
   * can be given outright, or read off the same entity as the values -
   * `frequencies` alongside `bands`, for a spectrum - in which case they are
   * formatted as frequencies: 20, 500, 1k, 16k.
   */
  _labels(n) {
    const c = this._cfg;
    let raw = Array.isArray(c.labels) ? c.labels : null;
    if (!raw && c.label_attribute && this._hass && c.entity) {
      const st = this._hass.states[c.entity];
      const list = st && st.attributes ? st.attributes[c.label_attribute] : null;
      if (Array.isArray(list)) raw = list.map(formatHz);
    }
    const out = [];
    for (let i = 0; i < n; i++) {
      out.push(raw && raw[i] != null ? String(raw[i]) : String(i + 1));
    }
    return out;
  }

  /** Whether this instance is the one on show. Two of them can share the
   * meter window - the channels and something else - and swap on an entity
   * without the card being rebuilt around them. */
  _syncVisible() {
    const when = this._cfg.show_when;
    if (!when || !when.entity) return;
    const st = this._hass ? this._hass.states[when.entity] : null;
    const want = st ? String(st.state) === String(when.state) : false;
    const now = this.style.display !== 'none';
    if (want === now) return;
    this.style.display = want ? 'block' : 'none';
    // Its subscription and its animation ride the on-screen gate, so the
    // hidden one costs nothing while it waits.
    this._onScreen = want && this._onScreen;
    this._syncSubscription();
  }

  _scale() {
    // Fixed, absolute, and deliberately not derived from the volume.
    return { ceiling: this._cfg.ceiling_db, floor: this._cfg.floor_db };
  }

  /** Columns, and their pitch and width in percent of this element's box.
   *
   * The 16-channel case returns the measured plate geometry untouched - its
   * pitch is not 100/16, it is what the artwork does, and the numbers under
   * the meter have to land on it. Any other count divides the window evenly
   * and keeps the plate's bar-to-pitch ratio, so a 31-band row looks like it
   * belongs to the same instrument.
   */
  _geom() {
    const n = Math.max(1, Number(this._cfg.bands) || GEOMETRY.channels);
    const inset = this._cfg.axis ? Math.max(0, Number(this._cfg.axis_inset) || 0) : 0;
    if (n === GEOMETRY.channels && !inset) {
      return { n, pitch: GEOMETRY.pitchPct, width: GEOMETRY.barWidthPct, inset: 0 };
    }
    const pitch = (100 - inset) / n;
    const dot = this._cfg.marker === 'dot';
    const frac = dot
      ? Math.max(0.05, Math.min(1, Number(this._cfg.dot_width_frac) || 0.55))
      : GEOMETRY.barWidthPct / GEOMETRY.pitchPct;
    return { n, pitch, width: pitch * frac, inset };
  }

  /** Where one column's marker goes, given its level as a percentage.
   *
   * A bar is clipped from the top so it grows out of the baseline; a dot is
   * placed at the level and nothing is drawn below it.
   */
  /** The dB scale up the left, and a rule across the window at each mark.
   *
   * Marks are the multiples of `axis_step` that fall strictly inside the
   * scale: the floor and the ceiling are the window's own edges and labelling
   * them says nothing the shape of the plot does not already say.
   */
  _buildAxis(geom) {
    const c = this._cfg;
    const floor = Number(c.floor_db);
    const ceiling = Number(c.ceiling_db);
    const span = ceiling - floor;
    const step = Math.abs(Number(c.axis_step) || 0);
    if (!(span > 0) || !step) return;

    const lo = Math.min(floor, ceiling);
    const hi = Math.max(floor, ceiling);
    for (let v = Math.ceil(lo / step) * step; v < hi; v += step) {
      if (v <= lo) continue;
      const pct = ((v - floor) / span) * 100;
      if (pct <= 0 || pct >= 100) continue;

      const rule = document.createElement('div');
      Object.assign(rule.style, {
        position: 'absolute',
        left: `${geom.inset}%`,
        right: '0',
        bottom: `${pct}%`,
        height: '1px',
        background: c.axis_grid,
        boxShadow: c.axis_grid_glow,
        pointerEvents: 'none',
      });
      this.appendChild(rule);
      this._chrome.push(rule);

      const inGutter = geom.inset > 0;
      const label = document.createElement('div');
      Object.assign(label.style, {
        position: 'absolute',
        left: '0',
        // In a gutter the number is centred on its rule and right-aligned
        // against the plot. With no gutter it perches on top of the rule at
        // the far left, out of the way of the line itself.
        width: inGutter ? `${Math.max(0, geom.inset - 1)}%` : 'auto',
        bottom: `${pct}%`,
        transform: inGutter ? 'translateY(50%)' : 'translateY(-0.1em)',
        textAlign: inGutter ? 'right' : 'left',
        fontSize: c.axis_size,
        lineHeight: '1',
        color: c.axis_color,
        pointerEvents: 'none',
        userSelect: 'none',
      });
      label.textContent = `${Math.round(v)}${c.axis_suffix}`;
      this.appendChild(label);
      this._chrome.push(label);
    }
  }

  /** How bright the dot on row `r` is. Full strength above the fade, and
   * evenly graded below it down to `dot_fade_min` on the bottom row. */
  _dotFade(r) {
    const rows = Math.max(0, Number(this._cfg.dot_fade_rows) || 0);
    if (r >= rows) return 1;
    const min = Math.max(0, Math.min(1, Number(this._cfg.dot_fade_min)));
    return +(min + (1 - min) * (r / rows)).toFixed(3);
  }

  _place(i, pct) {
    if (this._cfg.marker !== 'dot') {
      this._bars[i].style.clipPath = `inset(${100 - pct}% 0 0 0)`;
      return;
    }
    const dots = this._dots[i];
    if (!dots) return;
    // Round rather than floor, so a level sitting between two rows lands on
    // the nearer one instead of always reading low. Anything above silence
    // lights at least one dot: a band that is quiet but present should not
    // look the same as a band that is not there.
    let lit = Math.round((pct / 100) * dots.length);
    if (pct > 0 && lit === 0) lit = 1;
    if (lit === this._lit[i]) return;
    const head = this._cfg.dot_head_scale;
    const neck = this._cfg.dot_neck_color || this._cfg.dot_color;
    for (let r = 0; r < dots.length; r++) {
      const on = r < lit;
      const st = dots[r].style;
      const want = on ? 'block' : 'none';
      if (st.display !== want) st.display = want;
      // Only the top lit dot is scaled up, so the head moves with the level
      // instead of leaving a bigger dot behind at the old one.
      const scale = on && r === lit - 1 ? ` scale(${head})` : '';
      const tf = `translateY(50%)${scale}`;
      if (st.transform !== tf) st.transform = tf;
      // ...and only the one directly under it takes the neck colour. Both
      // are reassigned every time `lit` moves, so neither leaves a mark
      // behind at the row it used to occupy.
      const bg = on && r === lit - 2 ? neck : this._cfg.dot_color;
      if (st.background !== bg) st.background = bg;
    }
    this._lit[i] = lit;
  }

  _ballistic() {
    return Number(this._cfg.decay_db_s) > 0;
  }

  /* Ease every bar toward its target, fast up and slow down.
   *
   * Runs off requestAnimationFrame rather than the data rate: the unit pushes
   * at 4Hz at best, and a 250ms step is visible as a stair no matter what
   * easing is applied to it. Gated by the same on-screen test as the metering
   * subscription, so nothing animates behind another view. */
  _tick(now) {
    this._raf = 0;
    if (!this._ballistic() || !this._bars.length) return;

    const prev = this._lastTick || now;
    const dt = Math.min(100, Math.max(0, now - prev));  // clamp: a backgrounded
    this._lastTick = now;                               // tab returns a huge dt

    const attack = Math.max(1, Number(this._cfg.attack_ms) || 1);
    // dB/s -> %/s. The bar is drawn in percent of the meter box, and the box
    // spans `span` dB, so a fixed dB rate is a fixed percentage rate only
    // once you know the current scale. The scale moves with the volume, so
    // this is recomputed rather than cached.
    const span = this._span || 40;
    const fallPct = (Number(this._cfg.decay_db_s) / span) * 100 * (dt / 1000);
    const peakFallPct =
      (Number(this._cfg.peak_decay_db_s) / span) * 100 * (dt / 1000);
    const holdMs = Number(this._cfg.peak_hold_ms) || 0;

    // "is there still work to do", NOT "did anything move this frame". The
    // first frame after a kick has dt = 0 (there is no previous timestamp to
    // measure from), so nothing moves on it - and keying the loop off actual
    // movement made it stop dead on that very first frame, every time. The
    // bars then sat frozen at their last value while the data carried on
    // updating underneath them.
    let pending = false;
    for (let i = 0; i < this._bars.length; i++) {
      const target = this._target[i] || 0;
      let cur = this._shown[i] || 0;

      if (target > cur) {
        // Rising: a short time constant, so a transient lands inside one
        // frame without reading as a flicker.
        cur = cur + (target - cur) * (1 - Math.exp(-dt / attack));
        if (target - cur < 0.05) cur = target;
      } else if (cur > target) {
        // Falling: a constant dB/s, never past the target.
        cur = Math.max(target, cur - fallPct);
      }
      if (cur !== this._shown[i]) {
        this._shown[i] = cur;
        this._place(i, cur);
      }
      if (Math.abs(target - cur) > 0.01) pending = true;

      if (!this._peaks_el.length) continue;
      let peak = this._peaks[i] || 0;
      if (cur >= peak) {
        peak = cur;
        this._peakUntil[i] = now + holdMs;
      } else if (now >= (this._peakUntil[i] || 0)) {
        peak = Math.max(cur, peak - peakFallPct);
      }
      if (peak !== this._peakShown[i]) {
        this._peakShown[i] = peak;
        const el = this._peaks_el[i];
        // Hidden when the peak has caught the bar up: a marker sitting on top
        // of a full bar is just a brighter cap, which reads as an artefact.
        el.style.display = peak > 0.5 && peak > cur + 0.5 ? 'block' : 'none';
        el.style.bottom = `${peak}%`;
      }
      this._peaks[i] = peak;
      if (peak > cur + 0.01) pending = true;   // still has somewhere to fall
    }

    if (pending && this._onScreen && document.visibilityState === 'visible') {
      this._raf = requestAnimationFrame((t) => this._tick(t));
    }
  }

  _kick() {
    if (!this._ballistic() || this._raf) return;
    this._lastTick = 0;
    this._raf = requestAnimationFrame((t) => this._tick(t));
  }

  _render() {
    if (!this._bars.length) return;
    // With the unit away the window is dead space whatever is feeding it, so
    // the meter empties rather than carrying on measuring a room nobody is
    // listening to. Checked before the early return below, so an odd scale
    // can't strand the idle panel on screen.
    const gone = this._gone();
    const levels = gone ? null : this._levels();
    this._syncIdle(gone);
    if (gone !== this._chromeHidden) {
      this._chromeHidden = gone;
      for (const el of this._chrome || []) {
        // visibility, not display: the row under the meter is positioned
        // against the box and taking it out of flow would move things.
        el.style.visibility = gone ? 'hidden' : '';
      }
    }
    const { floor, ceiling } = this._scale();
    const span = ceiling - floor;
    if (!(span > 0)) return;
    this._span = span;

    for (let i = 0; i < this._bars.length; i++) {
      const db = levels && typeof levels[i] === 'number' ? levels[i] : null;
      let pct = 0;
      if (db !== null) {
        pct = ((db - floor) / span) * 100 * (Number(this._cfg.level_gain) || 1);
        pct = Math.max(0, Math.min(100, pct));
      }
      if (this._ballistic()) {
        this._target[i] = pct;
      } else {
        this._place(i, pct);
      }
    }
    this._kick();
  }

  // picture-elements asks elements for a size hint; ours is positioned
  // entirely by the YAML style block, so this is nominal.
  getCardSize() {
    return 1;
  }
}

if (!customElements.get('tide16-bars')) {
  customElements.define('tide16-bars', Tide16Bars);
}

/* =====================================================================
 * tide16-channels - the channel assignment legend under the plate.
 *
 * The 1-16 numbers baked into the plate only say which bar is which
 * OUTPUT; they don't say what that output drives. This renders the
 * device's own assignment (sensor.tide16_channel_levels attribute
 * `channel_names`, positionally aligned with `channels`) as one compact
 * row - "1 FL  2 FR  3 C ..." - so the meter can be read at a glance.
 *
 * Notes:
 *
 * 1. The names arrive as the device's long CamelCase words
 *    ("RearLeftSurround"), which are far too wide for one row. SHORT
 *    maps the known ones to standard speaker abbreviations; anything
 *    unrecognised falls back to word initials rather than being dropped,
 *    so a layout this map has never seen still renders something.
 *
 * 2. `channel_names` is SHORTER than `channels` - it stops at the last
 *    assigned output (11 entries for 7.2.2). The unassigned tail is
 *    hidden by default: those bars sit at the -122.5 dB idle floor and
 *    listing five empty slots is exactly the space this is meant to
 *    save. Set `show_unassigned: true` to see them.
 *
 * 3. On a card too narrow for one row it folds into two columns, 1-8 and
 *    9-16. Because the type is sized in cqw it would otherwise shrink with
 *    the card forever and "fit" at any width by becoming illegible; the px
 *    floor is what creates a real overflow point, and the container query
 *    folds it just before that point.
 *
 * 4. Repainting is gated on the name list actually changing. The bars
 *    element holds metering at 4 Hz while on screen, so this gets a hass
 *    object four times a second, and the assignment changes about once a
 *    year - rebuilding this DOM on every frame would be pure waste.
 */

// Device name -> standard abbreviation. Keys are lowercased on lookup.
const SHORT = {
  leftfront: 'FL',
  rightfront: 'FR',
  center: 'C',
  centre: 'C',
  // The device calls the first sub just "Sub"; numbered SW1 here so it
  // pairs visibly with SW2 rather than reading as a different kind of thing.
  sub: 'SW1',
  sub2: 'SW2',
  sub3: 'SW3',
  sub4: 'SW4',
  lfe: 'LFE',
  leftsurround: 'LS',
  rightsurround: 'RS',
  rearleftsurround: 'SBL',
  rearrightsurround: 'SBR',
  leftrearsurround: 'SBL',
  rightrearsurround: 'SBR',
  leftfrontoverhead: 'TFL',
  rightfrontoverhead: 'TFR',
  leftmiddleoverhead: 'TML',
  rightmiddleoverhead: 'TMR',
  leftrearoverhead: 'TRL',
  rightrearoverhead: 'TRR',
  leftfrontheight: 'FHL',
  rightfrontheight: 'FHR',
  leftrearheight: 'RHL',
  rightrearheight: 'RHR',
  leftwide: 'FWL',
  rightwide: 'FWR',
  leftfrontwide: 'FWL',
  rightfrontwide: 'FWR',
};

// 20 -> "20", 1000 -> "1k", 12500 -> "12.5k". Third-octave centres are the
// case in hand and they are the awkward ones: 31.5 and 12.5k have to keep
// their half, while 1000 must not print as 1.0k.
function formatHz(v) {
  const n = Number(v);
  if (!isFinite(n)) return String(v);
  if (n < 1000) return String(Math.round(n * 10) / 10);
  const k = Math.round((n / 1000) * 10) / 10;
  return `${k}k`;
}

// Fallback: "SomeNewSpeaker" -> "SNS". Digits stay attached to their word
// so a hypothetical "Sub5" still reads as S5 rather than S.
//
// The first alternative is what handles a name the user typed themselves in
// the unit's web UI rather than one the decoder assigned. A capital with no
// lowercase after it is a word in its own right: without it "L-Mix" matched
// only "Mix" and came out as "M", quietly dropping the half of the name that
// said which side it was. An all-capitals run is kept whole, since a name
// like "LM" is already an abbreviation and taking its initial would leave a
// single letter.
function abbreviate(name) {
  const key = String(name).replace(/[\s_-]/g, '');
  const hit = SHORT[key.toLowerCase()];
  if (hit) return hit;
  // Split on the separators before splitting on case, so a name typed in
  // lower case still reads as several words: "analyser left" is two words
  // and abbreviates AL, where treating it as one gave a bare A.
  const words = String(name)
    .trim()
    .split(/[\s_-]+/)
    .filter(Boolean)
    .flatMap((part) => part.match(/[A-Z]+(?![a-z])|[A-Z]?[a-z]+\d*|\d+/g) || [part]);
  if (!words.length) return key.slice(0, 4).toUpperCase();
  return words
    .map((w) =>
      (/^[A-Z]{2,}$/.test(w) ? w : w[0] + (w.match(/\d+$/) || [''])[0]).toUpperCase())
    .join('')
    .slice(0, 4);
}

const CH_DEFAULTS = {
  entity: 'sensor.tide16_channel_levels',
  attribute: 'channel_names',
  // Outputs whose name was typed into the unit's own web UI. Those are
  // printed as they were written; the decoder's own names are abbreviated.
  custom_attribute: 'custom_channels',
  channels: 16,
  show_unassigned: false,
  label: 'Output Channels:',
  // Drawn after the heading when the device is off and there is no
  // assignment list to render at all.
  placeholder: '-',
  // Sized in cqw like the rest of the card so it tracks the card width;
  // 1.2 sits just above the plate's own speaker-config label (1.144cqw).
  // The px floor is what makes the two-column fallback trigger at all -
  // see the note on `stack_below` below.
  font_size: '1.2cqw',
  min_font_size: '11px',
  gap: '1.35cqw',
  // Space between an output's number and its name.
  idx_gap: '0.3em',
  // Card width under which the row folds into two columns. Chosen to sit
  // just under where the px floor takes over from cqw (1.2cqw = 11px at a
  // 917px card), i.e. exactly where the row stops shrinking with the card
  // and would start running off the end of it.
  stack_below: '900px',
  column_gap: '2.4cqw',
  color: '#B7B8B8',
  index_color: 'rgba(183,184,184,0.42)',
  label_color: 'rgba(183,184,184,0.6)',
};

// Outputs per column once folded: 1-8 left, 9-16 right.
const CH_PER_COLUMN = 8;

// Tightest the legend's spacing may be squeezed to keep one line - see _fit.
// Both spacings scale together, so the ratio between them - and with it the
// grouping - holds all the way down; this is just the point where the row
// starts to look cramped. It takes all sixteen outputs named to reach it.
const CH_MIN_GAP_SCALE = 0.25;

class Tide16Channels extends HTMLElement {
  constructor() {
    super();
    this._cfg = { ...CH_DEFAULTS };
    this._hass = null;
    this._sig = null;
  }

  setConfig(config) {
    this._cfg = { ...CH_DEFAULTS, ...(config || {}) };
    this._sig = null;
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _build() {
    const c = this._cfg;
    // Shadow DOM purely so the @container rule below can't leak into the
    // rest of the dashboard. The container query still resolves against
    // ha-card's `container-type: inline-size` - container lookup walks the
    // flat tree, so the shadow boundary is not in the way.
    const root = this.shadowRoot || this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        :host { display: block; position: absolute; }
        .row {
          display: flex;
          flex-wrap: wrap;
          justify-content: flex-start;
          align-items: baseline;
          gap: calc(${c.gap} * 0.45) ${c.gap};
          font-size: max(${c.min_font_size}, ${c.font_size});
          font-weight: 300;
          line-height: 1.35;
          letter-spacing: 0.05em;
          white-space: nowrap;
          color: ${c.color};
        }
        .lead { color: ${c.label_color}; }
        .idx {
          color: ${c.index_color};
          /* Scaled by _fit along with the gaps between entries, so the
             space inside an entry stays visibly smaller than the space
             between two of them however tight the row gets - that ratio
             is what keeps "13 SW2 14 LM" reading as three pairs rather
             than one run of characters. */
          margin-right: calc(${c.idx_gap} * var(--t16-squeeze, 1));
        }
        .off { color: ${c.index_color}; }

        /* Folded form. Below this width the type has hit its px floor and
           stops scaling with the card, so a single row would overrun it.
           Every chip already carries a grid-row/grid-column - inert while
           this is a flex container, which is what lets the two layouts
           share one DOM and switch on width alone. */
        @container (max-width: ${c.stack_below}) {
          .row {
            display: grid;
            grid-template-columns: max-content max-content;
            column-gap: ${c.column_gap};
            row-gap: 0.15em;
            line-height: 1.25;
            justify-content: start;
          }
          /* right-align the numbers so the names form a clean column */
          .idx { display: inline-block; min-width: 1.5em; text-align: right; }
        }
      </style>
      <div class="row"></div>`;
    this._row = root.querySelector('.row');

    // The first `hass` usually lands before picture-elements has sized this
    // element, so the fit below has nothing to measure and the row is left
    // wrapped - and nothing re-renders it, because the names have not
    // changed. Re-fitting whenever the width actually changes covers both
    // that first sizing and a later card resize. Keyed on the width so
    // _fit's own effect on the row's height cannot feed back into it.
    this._observe();
  }

  _observe() {
    if (this._ro || !this._row || !window.ResizeObserver) return;
    this._ro = new ResizeObserver((entries) => {
      const w = entries[entries.length - 1].contentRect.width;
      if (w === this._width) return;
      this._width = w;
      this._refit();
    });
    this._ro.observe(this);
  }

  connectedCallback() {
    this._observe();
  }

  disconnectedCallback() {
    if (this._raf) {
      cancelAnimationFrame(this._raf);
      this._raf = null;
    }
    if (!this._ro) return;
    this._ro.disconnect();
    this._ro = null;
    this._width = null;
  }

  _names() {
    if (!this._hass) return null;
    const st = this._hass.states[this._cfg.entity];
    if (!st || !st.attributes) return null;
    const raw = st.attributes[this._cfg.attribute];
    return Array.isArray(raw) ? raw : null;
  }

  /** Output numbers, 1-based, whose name is the user's own words. */
  _custom() {
    if (!this._hass) return [];
    const st = this._hass.states[this._cfg.entity];
    const raw = st && st.attributes ? st.attributes[this._cfg.custom_attribute] : null;
    return Array.isArray(raw) ? raw.map(Number).filter((n) => n > 0) : [];
  }

  _render() {
    const names = this._names();
    const custom = this._custom();
    const sig = JSON.stringify([names, custom]);
    if (sig === this._sig) return;
    this._sig = sig;
    this._paint(names, custom);
    this._refit();
  }

  /** Fit now, and again on the next frame.
   *
   * The first paint usually happens before the card has resolved its own
   * width, and until it does, the container query that chooses between the
   * one-line row and the folded two-column form reports the folded one - so
   * _fit sees a deliberately multi-line layout and correctly leaves it alone.
   * Nothing repaints afterwards, because the names have not changed, and the
   * row stays wrapped off the bottom of the plate. A second pass one frame
   * later runs against the real geometry.
   */
  _refit() {
    this._fit();
    if (!window.requestAnimationFrame) return;
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = requestAnimationFrame(() => {
      this._raf = null;
      this._fit();
    });
  }

  /** Close the gaps up, and only the gaps, if the row would run onto a
   * second line.
   *
   * The strip is one line of black screen with nothing under it, so a second
   * line falls off the bottom of the plate.  It only comes up when the unit
   * names more outputs than a 7.2.4 layout assigns - an output driven by hand
   * through the routing matrix, named in the unit's own web UI - which is a
   * couple of entries more than the strip was drawn for.
   *
   * The type is deliberately left alone: at 15 entries the words themselves
   * take 544 of the 616 available px, so the row fits comfortably at full
   * size once the 8px between entries comes down to about 5.  Shrinking the
   * font instead would make the legend smaller than everything else printed
   * on the plate to buy space that the spacing already has.
   *
   * All sixteen outputs named is the worst case there is, and it fits.
   */
  _fit() {
    const row = this._row;
    if (!row) return;
    row.style.gap = '';
    row.style.removeProperty('--t16-squeeze');
    // The folded two-column form is many lines on purpose - leave it be.
    if (getComputedStyle(row).display === 'grid') return;

    const wraps = () => {
      const line = parseFloat(getComputedStyle(row).lineHeight);
      return line > 0 && row.getBoundingClientRect().height > line * 1.4;
    };
    if (!wraps()) return;

    const c = this._cfg;
    for (let f = 0.85; f >= CH_MIN_GAP_SCALE; f -= 0.05) {
      row.style.gap = `calc(${c.gap} * 0.45 * ${f}) calc(${c.gap} * ${f})`;
      row.style.setProperty('--t16-squeeze', String(f));
      if (!wraps()) return;
    }
    // Nothing more to give. The tightest spacing stays rather than going
    // back to normal: there is no second line to wrap onto here - it falls
    // off the bottom of the plate - so the most that fits on one line is the
    // most the reader gets to see.
  }

  _paint(names, custom) {
    if (!this._row) return;
    this._row.innerHTML = '';

    if (this._cfg.label) {
      const lead = document.createElement('span');
      lead.className = 'lead';
      lead.textContent = this._cfg.label;
      // Folded, the label heads both columns instead of sitting in one.
      lead.style.gridColumn = '1 / -1';
      lead.style.gridRow = '1';
      this._row.appendChild(lead);
    }

    // Device down: the assignment list doesn't exist at all, so there is
    // nothing to number. One dash after the heading, rather than sixteen
    // of them or - as this used to do - dropping the heading too and
    // leaving a silent gap under the plate.
    if (!names) {
      const gone = document.createElement('span');
      gone.className = 'off';
      gone.textContent = this._cfg.placeholder;
      gone.style.gridColumn = '1';
      gone.style.gridRow = '2';
      this._row.appendChild(gone);
      return;
    }

    const total = this._cfg.show_unassigned
      ? Math.max(this._cfg.channels, names.length)
      : names.length;

    for (let i = 0; i < total; i++) {
      const name = names[i];
      const chip = document.createElement('span');
      // Inert in the flex layout, honoured in the folded grid: outputs
      // 1-8 down the left column, 9-16 down the right. Row 1 is the label.
      chip.style.gridColumn = String(Math.floor(i / CH_PER_COLUMN) + 1);
      chip.style.gridRow = String((i % CH_PER_COLUMN) + 2);
      // Full device name on hover - the abbreviations are standard but
      // "SBL" vs "TRL" is worth being able to check without leaving the page.
      if (name) chip.title = `Output ${i + 1}: ${name}`;

      const idx = document.createElement('span');
      idx.className = 'idx';
      idx.textContent = String(i + 1);
      chip.appendChild(idx);

      const label = document.createElement('span');
      if (!name) label.className = 'off';
      // A name from the unit's web UI is printed as it was typed - it is
      // already whatever length its author wanted. Only the decoder's own
      // enum names get shortened, since those are things like
      // "RightRearOverhead".
      const own = (custom || []).indexOf(i + 1) !== -1;
      label.textContent = name ? (own ? name : abbreviate(name)) : '—';
      chip.appendChild(label);

      this._row.appendChild(chip);
    }
  }

  getCardSize() {
    return 1;
  }
}

if (!customElements.get('tide16-channels')) {
  customElements.define('tide16-channels', Tide16Channels);
}

/* =====================================================================
 * tide16-toggle - a small two-state button printed on the faceplate.
 *
 * Made for choosing what the meter window is showing - the unit's own DSP
 * channels, or something else measured about the same system - but it is
 * just a button over an entity with a short label per state. Tapping it
 * steps to the next state.
 *
 * It drives an entity rather than holding the choice itself, so the setting
 * survives a reload, reads the same on every screen looking at the
 * dashboard, and can be moved by a script or a scene like anything else.
 * input_select and input_boolean are both handled.
 * ===================================================================== */

const TOGGLE_DEFAULTS = {
  entity: null,
  // state -> what to print. A state with no entry prints itself.
  labels: {},
  // state -> what colour to print it in, for a button whose label does not
  // change with its state. A state with no entry uses `color`.
  colors: {},
  // Optional mark before the label. Drawn as a mask filled with the button's
  // own colour rather than as an image, so it dims and brightens with the
  // text instead of sitting there at full strength while the label greys out.
  icon: null,
  icon_size: '0.95em',
  icon_gap: '0.34em',
  size: '0.844cqw',
  weight: '500',
  color: '#E7E8E8',
  background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.28)',
  radius: '0.18cqw',
  padding: '0.12cqw 0.36cqw',
  active_color: '#FFFFFF',
  placeholder: '--',
};

class Tide16Toggle extends HTMLElement {
  constructor() {
    super();
    this._cfg = { ...TOGGLE_DEFAULTS };
    this._hass = null;
    this._shown = null;
  }

  setConfig(config) {
    this._cfg = { ...TOGGLE_DEFAULTS, ...(config || {}) };
    this._shown = null;
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _build() {
    const c = this._cfg;
    const root = this.shadowRoot || this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        /* flex, not block: an inline-block button in a block host sits on a
           text baseline, and the leading under it pushed the button below
           the cell it was positioned into. */
        :host { display: flex; position: absolute; align-items: flex-start; }
        .btn {
          display: inline-block;
          font-size: ${c.size};
          font-weight: ${c.weight};
          line-height: 1;
          letter-spacing: 0.05em;
          color: ${c.color};
          background: ${c.background};
          border: ${c.border};
          border-radius: ${c.radius};
          padding: ${c.padding};
          white-space: nowrap;
          user-select: none;
          cursor: pointer;
        }
        .btn:active {
          color: ${c.active_color};
          filter: brightness(1.5);
        }
        .ico {
          display: inline-block;
          width: ${c.icon_size};
          height: ${c.icon_size};
          margin-right: ${c.icon_gap};
          /* the glyph is the mask, the colour is the button's own */
          background: currentColor;
          -webkit-mask: var(--t16-icon) center / contain no-repeat;
          mask: var(--t16-icon) center / contain no-repeat;
          /* sits on the text's optical centre, not its baseline */
          vertical-align: -0.12em;
        }
      </style>
      <span class="btn">${c.icon ? '<i class="ico"></i>' : ''}<span class="txt"></span></span>`;
    this._btn = root.querySelector('.btn');
    this._txt = root.querySelector('.txt');
    if (c.icon) {
      this._btn.style.setProperty('--t16-icon', `url("${c.icon}")`);
    }
    this._btn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      this._step();
    });
  }

  _state() {
    const st = this._hass && this._cfg.entity
      ? this._hass.states[this._cfg.entity] : null;
    return st ? String(st.state) : null;
  }

  _render() {
    if (!this._btn) return;
    const state = this._state();
    if (state === this._shown) return;
    this._shown = state;
    const label = state === null
      ? this._cfg.placeholder
      : (this._cfg.labels[state] != null ? this._cfg.labels[state] : state);
    this._txt.textContent = String(label);
    // A button that always says the same thing has to show its state some
    // other way, so the colour is it.
    const colour = state !== null ? this._cfg.colors[state] : null;
    this._btn.style.color = colour || '';
  }

  /** Step to the next state. The button shows what IS displayed, so tapping
   * it moves on rather than toggling something named on the button - which
   * is the same way the unit's own front panel behaves. */
  _step() {
    const c = this._cfg;
    if (!this._hass || !c.entity) return;
    const st = this._hass.states[c.entity];
    if (!st) return;
    const [domain] = c.entity.split('.');
    if (domain === 'input_boolean' || domain === 'switch') {
      this._hass.callService(domain, 'toggle', { entity_id: c.entity });
      return;
    }
    const options = (st.attributes && st.attributes.options) || [];
    if (!options.length) return;
    const next = options[(options.indexOf(st.state) + 1) % options.length];
    this._hass.callService('input_select', 'select_option', {
      entity_id: c.entity,
      option: next,
    });
  }

  getCardSize() {
    return 1;
  }
}

/* =====================================================================
 * tide16-buttons - the scene button column on the faceplate.
 *
 * A vertical stack of fixed-ratio buttons inside whatever box the YAML
 * gives it. The ratio is the point: the element sizes itself from the box
 * WIDTH via aspect-ratio, so re-positioning or resizing the box can never
 * produce squashed or stretched buttons - only different spacing.
 *
 * `gap` picks how the slack is spent. A justify-content keyword
 * ("space-between", the default) spreads the buttons across the whole box.
 * Any length instead ("1.53cqw") sets a fixed inter-button gap and the
 * stack is pinned to the BOTTOM of the box - which is the edge the YAML
 * aligns to the plate's screen, so the buttons stay registered to it and
 * the slack collects at the top, under the title.
 *
 * Buttons are inert until a `tap` is configured. Each entry takes
 * {color, label?, hint?, tap: {action, data}} where action is a service in
 * "domain.service" form - e.g.
 *   buttons:
 *     - color: "#D93A2B"
 *       hint: Movie Time
 *       tap: {action: scene.turn_on, data: {entity_id: scene.movie}}
 *
 * `hint` is the button's hover text, and on a colour-only button it is
 * the only name the thing has - worth setting.
 *
 * An optional `title` rides ABOVE the box (bottom: 100%), deliberately
 * outside it: the box IS the button column's geometry - its bottom edge
 * is aligned to the plate's screen from the YAML - so a heading that
 * consumed box height would drag the buttons off that alignment. As a
 * shadow child it centres on the column for free, and it inherits the
 * frontend font, so it matches the live readouts on the screen.
 */

const BTN_DEFAULTS = {
  ratio: '7 / 2', // width / height of each button
  gap: 'space-between', // justify-content keyword, or a length (see above)
  radius: '3px',
  title: null, // optional heading above the column
  title_size: '1.05cqw', // between the source and speaker-config readouts
  title_color: '#BFC0C0',
  title_gap: '0.5cqw', // clearance between heading and first button
  buttons: [{ color: '#D93A2B' }, { color: '#2FA84F' }, { color: '#E8C22E' }, { color: '#2F6FD0' }],
};

class Tide16Buttons extends HTMLElement {
  constructor() {
    super();
    this._cfg = { ...BTN_DEFAULTS };
    this._hass = null;
  }

  setConfig(config) {
    this._cfg = { ...BTN_DEFAULTS, ...(config || {}) };
    if (!Array.isArray(this._cfg.buttons) || !this._cfg.buttons.length) {
      throw new Error('tide16-buttons: `buttons` must be a non-empty list');
    }
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _build() {
    const c = this._cfg;
    // a justify-content keyword spreads the buttons; anything else is a
    // length, i.e. a fixed gap with the stack held against the box bottom
    const spread = /^(space-between|space-around|space-evenly|flex-start|flex-end|center)$/.test(
      String(c.gap).trim()
    );
    const root = this.shadowRoot || this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        :host { display: block; position: absolute; }
        .col {
          display: flex;
          flex-direction: column;
          justify-content: ${spread ? c.gap : 'flex-end'};
          gap: ${spread ? '0' : c.gap};
          height: 100%;
        }
        .title {
          position: absolute;
          bottom: 100%;
          /* centred on the column, NOT laid out across it: the heading is
             normally wider than a button, and a width:100% box that the
             text overflows gets start-aligned by the engine no matter what
             text-align says - which hangs the whole word off the column's
             left edge. Sized to its own content and pulled back by half,
             it stays centred on the buttons at any width. */
          left: 50%;
          transform: translateX(-50%);
          width: max-content;
          padding-bottom: ${c.title_gap};
          text-align: center;
          /* no font-family: inherit the frontend's, same as the state
             labels printed on the screen */
          font-size: ${c.title_size};
          font-weight: 300;
          line-height: 1;
          letter-spacing: 0.08em;
          color: ${c.title_color};
          white-space: nowrap;
          pointer-events: none;
        }
        .btn {
          width: 100%;
          aspect-ratio: ${c.ratio};
          flex: none;
          border-radius: ${c.radius};
          /* faint top highlight + seated edge, so they read as physical
             buttons on a photoreal plate rather than flat CSS swatches */
          background-image: linear-gradient(
            to bottom, rgba(255,255,255,0.22), rgba(255,255,255,0) 45%,
            rgba(0,0,0,0.18) 100%);
          box-shadow:
            inset 0 0 0 1px rgba(0,0,0,0.35),
            0 1px 2px rgba(0,0,0,0.45);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1cqw;
          font-weight: 400;
          letter-spacing: 0.08em;
          color: rgba(0,0,0,0.72);
          user-select: none;
        }
        .btn[data-tap] { cursor: pointer; }
        .btn[data-tap]:active { filter: brightness(0.86); }
      </style>
      ${c.title ? '<div class="title"></div>' : ''}
      <div class="col"></div>`;

    // textContent, not interpolated into the template above, so a title
    // with markup in it stays text
    if (c.title) root.querySelector('.title').textContent = c.title;

    const col = root.querySelector('.col');
    c.buttons.forEach((b, i) => {
      const el = document.createElement('div');
      el.className = 'btn';
      el.style.backgroundColor = b.color || '#888';
      if (b.label) el.textContent = b.label;
      // A colour-only button says nothing about what it does, so the
      // hover text is the only label it has. `hint` first, then whatever
      // `label` is printed on it; without either it stays untitled rather
      // than surfacing a raw entity_id.
      const hint = b.hint != null ? String(b.hint) : b.label ? String(b.label) : '';
      if (b.tap && b.tap.action) {
        el.dataset.tap = '';
        el.addEventListener('click', () => this._fire(b.tap));
        if (hint) el.title = hint;
      }
      col.appendChild(el);
    });
  }

  _fire(tap) {
    if (!this._hass) return;
    const [domain, service] = String(tap.action).split('.');
    if (!domain || !service) return;
    this._hass.callService(domain, service, tap.data || {});
  }

  getCardSize() {
    return 1;
  }
}

if (!customElements.get('tide16-buttons')) {
  customElements.define('tide16-buttons', Tide16Buttons);
}

/* =====================================================================
 * tide16-glyph - one PNG on the plate, with a tap and hover text.
 *
 * Exists because picture-elements' own `image` element can't be hovered
 * reliably here: it does accept a `title`, but it hangs it on the inner
 * <hui-image> while its clickable wrapper puts another div over the top,
 * so the cursor lands on an element that has no title in its ancestry and
 * no tooltip ever appears. Owning the element means the title sits on the
 * host, which IS the hover target - the same thing that makes hover work
 * on the buttons, inputs and knob labels.
 *
 * {image, hint?, tap?: {action, data}}. The box sets the size, as with
 * everything else on this plate: the PNG fills the width and keeps its
 * own aspect. Untapped it stays inert and takes no pointer events, so it
 * can't swallow a click meant for the plate underneath.
 *
 * `button: true` sinks the glyph into a concave panel button - a round
 * dish with a 1px rim, lit from below so it reads as milled INTO the
 * plate rather than sitting on it. With it, the box is the BUTTON and
 * `icon_scale` (0.8 default) is the glyph inside, so give the box a
 * `height` as well as a `width` or the dish will not be round.
 *
 * `color_entity` paints the art from live state - {color_entity,
 * color_on?, color_off?, on_states?}. The PNG stops being an image and
 * becomes a MASK: its alpha is the shape and the colour is the element's
 * own background, so one file serves both states and the hex is exact
 * rather than whatever a filter chain lands on. Needs flat line art on
 * transparency, which is what the plate's glyphs are.
 * `on_states` defaults to ['on']; ANY other state - including a missing
 * entity, unknown or unavailable - is off. That fail-safe is deliberate
 * for the power glyph: the Tide16 drops off the network in standby, so
 * "I cannot see it" and "it is off" are the same fact.
 * `color` is the same masking with no entity behind it - one flat colour.
 *
 * `busy_colors` makes a TAP flash the glyph until the unit answers again.
 * A reboot takes the Tide16 off the network for most of a minute and the
 * whole panel dashes out while it is gone, so without this the button
 * looks like it did nothing at all. The cycle IS the progress bar:
 *   busy_colors    the colours to step through, one per interval
 *   busy_interval  ms per step (1000)
 *   busy_min_steps steps to show before liveness may end it (5)
 *   busy_timeout   hard stop in ms (60000), after which it rests again
 *   busy_entity    what "answering again" means (defaults to color_entity)
 *   busy_live_states  states that count as answering (['on'])
 * Two things make the wait honest, and both were learned the hard way:
 * the run must SEE the entity go down before a live reading can end it,
 * and down has to be a whitelist - a rebooting Tide16 reports `off`, not
 * `unavailable`, so "not unavailable" reads a dead unit as a live one.
 * Either exit lands back on the resting colour - the glyph never stays
 * stuck mid-cycle, however the wait ends.
 */

// Fallbacks for a `color_entity` glyph that names no colours of its own.
// The off colour is the plate's own glyph grey, so an untinted-looking
// glyph is what you get if only the entity is given.
const GLYPH_TINT_ON = '#BFC0C0';
const GLYPH_TINT_OFF = '#BFC0C0';
const GLYPH_BUSY_INTERVAL = 1000;
const GLYPH_BUSY_MIN_STEPS = 5;
const GLYPH_BUSY_TIMEOUT = 60000;

class Tide16Glyph extends HTMLElement {
  constructor() {
    super();
    this._cfg = {};
    this._hass = null;
  }

  setConfig(config) {
    this._cfg = { ...(config || {}) };
    if (!this._cfg.image) {
      throw new Error('tide16-glyph: `image` is required');
    }
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    this._paint();
  }

  /* The colour this glyph rests at: state-driven if it has an entity,
     otherwise its one flat `color`. */
  _restColor() {
    const c = this._cfg;
    if (c.color_entity && this._hass) {
      const st = this._hass.states[c.color_entity];
      const on = !!st && this._onStates.includes(String(st.state).toLowerCase());
      return on ? c.color_on || GLYPH_TINT_ON : c.color_off || GLYPH_TINT_OFF;
    }
    return c.color || c.color_off || GLYPH_TINT_OFF;
  }

  /* Repaint a masked glyph. hass ticks at 4 Hz while the meter is on
     screen, so this writes to the DOM only when the colour actually
     changes - and never while a busy run is on, which owns the colour
     until it ends. */
  _paint() {
    if (!this._ink || this._busy) return;
    const col = this._restColor();
    if (col === this._col) return;
    this._col = col;
    this._ink.style.background = col;
  }

  /* Is the thing this glyph waits on answering?
     Whitelist, not blacklist, and that is the whole point: through a
     reboot the Tide16's media_player does NOT go unavailable, it reports
     `off` with status "not connected" - so anything that merely excluded
     unknown/unavailable called a rebooting unit live and ended the wait
     before it had begun. Only the states named in `busy_live_states`
     (default ['on']) count as answering. */
  _isLive() {
    const c = this._cfg;
    const ent = c.busy_entity || c.color_entity;
    if (!ent || !this._hass) return false;
    const st = this._hass.states[ent];
    return !!st && this._liveStates.includes(String(st.state).toLowerCase());
  }

  _startBusy() {
    const c = this._cfg;
    if (!this._ink) return;
    const cols = Array.isArray(c.busy_colors) && c.busy_colors.length
      ? c.busy_colors
      : [this._restColor()];
    const every = Number(c.busy_interval) || GLYPH_BUSY_INTERVAL;
    const minSteps =
      c.busy_min_steps == null ? GLYPH_BUSY_MIN_STEPS : Number(c.busy_min_steps);
    const limit = Number(c.busy_timeout) || GLYPH_BUSY_TIMEOUT;
    this._stopBusy();
    this._busy = true;
    let step = 0;
    // A unit can only come BACK if it went away first. For the seconds
    // between the press and the unit actually dropping off the network it
    // is still answering, so "live" on its own would end the cycle a beat
    // after it started - which is exactly what it did. The run therefore
    // waits to SEE it go down, and only then treats live as "it's back".
    let seenDown = false;
    const tick = () => {
      // paint first, so the very first frame acknowledges the press
      this._col = cols[step % cols.length];
      this._ink.style.background = this._col;
      step += 1;
      const live = this._isLive();
      if (!live) seenDown = true;
      if ((live && seenDown && step >= minSteps) || step * every >= limit) {
        this._stopBusy();
        return;
      }
      this._busyTimer = setTimeout(tick, every);
    };
    tick();
  }

  /* Always the way out of a busy run - both exits and an unmount come
     through here, so the glyph can never be left stuck mid-cycle. */
  _stopBusy() {
    if (this._busyTimer) clearTimeout(this._busyTimer);
    this._busyTimer = null;
    this._busy = false;
    this._col = null; // the cycle wrote colours behind _paint's back
    this._paint();
  }

  disconnectedCallback() {
    this._stopBusy();
  }

  _build() {
    const c = this._cfg;
    const root = this.shadowRoot || this.attachShadow({ mode: 'open' });
    const tappable = !!(c.tap && c.tap.action);
    // `button: true` wraps the glyph in a concave panel button. The BOX is
    // the button, and the icon is `icon_scale` of it - width and height
    // both, with object-fit: contain, so the scale is exact whatever the
    // art's aspect. Sizing by width alone would shrink a tall glyph less
    // than a square one and the pair would stop matching.
    const s = c.icon_scale == null ? 0.8 : Number(c.icon_scale);
    const pct = (s * 100).toFixed(2);
    const btn = !!c.button;
    // A tinted glyph is a masked DIV, not an <img> - see the doc block.
    // `ink` is whichever of the two this instance ended up with, so the
    // sizing and :active rules below stay written once.
    const tint = !!(c.color_entity || c.color || c.busy_colors);
    const ink = tint ? '.ink' : 'img';
    const inkEl = tint ? '<div class="ink"></div>' : '<img>';
    this._onStates = (Array.isArray(c.on_states) ? c.on_states : ['on']).map((v) =>
      String(v).toLowerCase()
    );
    this._liveStates = (
      Array.isArray(c.busy_live_states) ? c.busy_live_states : ['on']
    ).map((v) => String(v).toLowerCase());
    root.innerHTML = `
      <style>
        :host {
          display: block;
          position: absolute;
          pointer-events: ${tappable ? 'auto' : 'none'};
          cursor: ${tappable ? 'pointer' : 'default'};
        }
        ${
          btn
            ? `
        /* A shallow dish milled into the panel. The gradient is lit from
           BELOW - bright at the bottom, dark at the top - which is what
           reads as concave; the same gradient flipped reads as a dome.
           The inset shadow up top is the rim casting into the well, the
           inset highlight at the bottom is the light it bounces back, and
           the 1px outer bottom line is the panel's own cut edge catching
           light, which is what makes it sit flush rather than float. */
        .btn {
          position: absolute;
          inset: 0;
          border-radius: 50%;
          display: grid;
          place-items: center;
          /* The dish sits well ABOVE the plate's own near-black (#0e0e0e)
             so the component reads as hardware rather than as a hole.
             Bottom-lit: #14161a at the top wall climbing to #4e5157 at
             the bottom, a ~58-luma sweep across the face. */
          background: radial-gradient(120% 120% at 50% 128%,
                                      #4e5157 0%, #303338 38%, #1d1f23 72%, #14161a 100%);
          border: 1px solid ${c.button_border || '#7d828b'};
          box-shadow:
            /* rim casting into the well - the main concavity cue */
            inset 0 5px 7px -2px rgba(0, 0, 0, 0.95),
            /* light bouncing off the lower inner wall */
            inset 0 -4px 6px -2px rgba(255, 255, 255, 0.30),
            /* crisp inner darkening so the wall meets the rim, not fades */
            inset 0 0 0 1px rgba(0, 0, 0, 0.55),
            /* panel surface catching light on the upper lip of the hole,
               and dropping into shadow below it - an inset reads the
               OPPOSITE way round to a raised button here */
            0 -1px 0 rgba(255, 255, 255, 0.13),
            0 2px 3px rgba(0, 0, 0, 0.75);
        }
        ${ink} {
          display: block;
          width: ${pct}%;
          height: ${pct}%;
          object-fit: contain;
        }
        :host(:hover) .btn { border-color: ${c.button_border_hover || '#a3a8b1'}; }
        /* pressed: deepen the dish and sink the icon a hair */
        :host(:active) .btn {
          background: radial-gradient(120% 120% at 50% 128%,
                                      #3a3d42 0%, #232629 38%, #15171a 72%, #0e1013 100%);
          box-shadow:
            inset 0 6px 9px -2px rgba(0, 0, 0, 1),
            inset 0 0 0 1px rgba(0, 0, 0, 0.6);
        }
        :host(:active) ${ink} { filter: brightness(0.75); transform: translateY(0.5px); }`
            : `
        /* A masked glyph has no intrinsic size to keep an aspect from, so
           it fills the box and the BOX carries the art's aspect. An <img>
           still sizes itself off the file, exactly as before. */
        ${ink} { display: block; width: 100%; height: ${tint ? '100%' : 'auto'}; }
        :host(:active) ${ink} { filter: brightness(0.7); }`
        }
        ${
          tint
            ? `
        /* Both spellings: -webkit-mask is still the one some Chromium
           builds honour on the shorthand. A contain fit matches the
           object-fit an <img> would have used, so swapping to a mask does
           not resize the art. The colour here is only the pre-paint
           value - _paint owns it from the first hass tick. */
        .ink {
          -webkit-mask: url("${c.image}") center / contain no-repeat;
          mask: url("${c.image}") center / contain no-repeat;
          background: ${c.color || c.color_off || GLYPH_TINT_OFF};
        }`
            : ''
        }
      </style>
      ${btn ? `<div class="btn">${inkEl}</div>` : inkEl}`;
    this._ink = root.querySelector('.ink');
    this._col = null;
    const img = root.querySelector('img');
    if (img) {
      img.src = c.image;
      // alt, not the tooltip: the hover text belongs on the host, which is
      // what the cursor actually lands on
      img.alt = c.hint == null ? '' : String(c.hint);
    }
    if (c.hint != null) this.title = String(c.hint);
    if (tappable) {
      this.onclick = () => {
        this._fire(c.tap);
        if (c.busy_colors) this._startBusy();
      };
    }
    this._paint();
  }

  _fire(tap) {
    if (!this._hass) return;
    const [domain, service] = String(tap.action).split('.');
    if (!domain || !service) return;
    this._hass.callService(domain, service, tap.data || {});
  }

  getCardSize() {
    return 1;
  }
}

if (!customElements.get('tide16-glyph')) {
  customElements.define('tide16-glyph', Tide16Glyph);
}

/* =====================================================================
 * tide16-knob-labels - text laid out around a knob, by clock position.
 *
 * The YAML box is the KNOB, not the text: give it the knob's bounding
 * square on the plate and every label places itself outside that circle.
 * That is the whole point - one box to measure, and `gap` is then a real
 * clearance from the knob's edge that stays honest at every angle,
 * instead of eight hand-tuned left/top pairs that drift the moment the
 * card is rescaled.
 *
 * Each label is {at, text, tap?} where `at` is a clock position (12, 1,
 * 2, 3, 6, 9, 10, 11). Hours map to angles the usual way - 12 is up, 3
 * is right - and a FRACTION is a fraction of an hour, so 4.5 is half
 * past four: the 135-degree diagonal, which whole hours cannot reach.
 * The label is then pushed out along that ray by half its own
 * box, so what ends up `gap` from the circle is the label's NEAREST
 * edge: bottom at 12, top at 6, left at 3, right at 9, and the
 * corresponding corner on the diagonals.
 *
 * `tap` is the same {action, data} shape the scene buttons take, e.g.
 *   - at: 3
 *     text: "Vol: +10"
 *     tap: {action: script.turn_on, data: {entity_id: script.x}}
 * A tappable label carries hover text: `hint`, or its own rows joined
 * back into one line.
 * A label without one stays inert and does not take pointer events, so
 * it can't swallow a click meant for the plate underneath.
 *
 * No font-family: like the scene-button heading it inherits the
 * frontend's, so the labels match the readouts printed on the screen.
 */

const KNOB_DEFAULTS = {
  gap: '0.381cqw', // clearance from the knob edge (10px of the 2622 canvas)
  color: '#000',
  size: '1.05cqw', // same as the scene-button heading
  weight: '400',
  line_gap: '0.05cqw', // between the stacked rows of one label
  labels: [],
};

// clock hour -> angle in radians, measured CCW from 3 o'clock
const HOUR_ANGLE = (h) => ((3 - (h % 12)) * 30 * Math.PI) / 180;

class Tide16KnobLabels extends HTMLElement {
  constructor() {
    super();
    this._cfg = { ...KNOB_DEFAULTS };
    this._hass = null;
  }

  setConfig(config) {
    this._cfg = { ...KNOB_DEFAULTS, ...(config || {}) };
    if (!Array.isArray(this._cfg.labels) || !this._cfg.labels.length) {
      throw new Error('tide16-knob-labels: `labels` must be a non-empty list');
    }
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _build() {
    const c = this._cfg;
    const root = this.shadowRoot || this.attachShadow({ mode: 'open' });
    const round = (n) => Number(n.toFixed(4));

    const items = c.labels
      .map((l, i) => {
        const a = HOUR_ANGLE(Number(l.at));
        const cos = round(Math.cos(a));
        const sin = round(Math.sin(a));
        // the point on the circle for this hour, then `gap` further out
        const px = round(50 + 50 * cos);
        const py = round(50 - 50 * sin);
        // a stacked label has to know which way to align: the ray decides.
        // Labels out to the side grow away from the knob, the ones at 12
        // and 6 straddle its centreline.
        const align = cos > 0.1 ? 'left' : cos < -0.1 ? 'right' : 'center';
        return `
          .l${i} {
            left: calc(${px}% + (${c.gap} * ${cos}));
            top: calc(${py}% - (${c.gap} * ${sin}));
            text-align: ${align};
            /* push the box out by half of itself along the same ray, so
               its near edge - not its centre - lands on that point. With a
               stacked label the box is taller, so the whole stack simply
               sits further out; the near EDGE is still gap from the rim. */
            transform: translate(${round(-50 + 50 * cos)}%, ${round(-50 - 50 * sin)}%);
          }`;
      })
      .join('');

    root.innerHTML = `
      <style>
        /* the host box IS the knob, so it must not eat clicks - only the
           labels that actually have a tap turn pointer events back on */
        :host { display: block; position: absolute; pointer-events: none; }
        .wrap { position: relative; width: 100%; height: 100%; pointer-events: none; }
        .l {
          position: absolute;
          font-size: ${c.size};
          font-weight: ${c.weight};
          line-height: 1;
          letter-spacing: 0.04em;
          color: ${c.color};
          white-space: nowrap;
          user-select: none;
          pointer-events: none;
        }
        .l[data-tap] { pointer-events: auto; cursor: pointer; }
        .l[data-tap]:active { opacity: 0.55; }
        .ln + .ln { padding-top: ${c.line_gap}; }
        ${items}
      </style>
      <div class="wrap"></div>`;

    const wrap = root.querySelector('.wrap');
    c.labels.forEach((l, i) => {
      const el = document.createElement('div');
      el.className = `l l${i}`;
      // `text` takes a list as readily as a string - a list stacks, one
      // row per entry, which is how "Mute:" / "On" is drawn
      const lines = l.text == null ? [] : Array.isArray(l.text) ? l.text : [l.text];
      lines.forEach((t) => {
        const ln = document.createElement('div');
        ln.className = 'ln';
        ln.textContent = String(t);
        el.appendChild(ln);
      });
      if (l.tap && l.tap.action) {
        el.dataset.tap = '';
        el.addEventListener('click', () => this._fire(l.tap));
        // hover text: `hint`, else the label's own rows run back into one
        // line - "Mute:" / "On" reads as "Mute: On". The inert labels get
        // none; they don't take pointer events, so it would never show.
        const hint = l.hint != null ? String(l.hint) : lines.join(' ');
        if (hint) el.title = hint;
      }
      wrap.appendChild(el);
    });
  }

  _fire(tap) {
    if (!this._hass) return;
    const [domain, service] = String(tap.action).split('.');
    if (!domain || !service) return;
    this._hass.callService(domain, service, tap.data || {});
  }

  getCardSize() {
    return 1;
  }
}

if (!customElements.get('tide16-knob-labels')) {
  customElements.define('tide16-knob-labels', Tide16KnobLabels);
}

/* =====================================================================
 * tide16-readout - a titled block of label/value lines on the screen.
 *
 * The plate's screen is a grid of cells with the rules baked into the
 * artwork; this fills one of them the way the device's own UI does - a
 * dim heading over one or more live lines, e.g.
 *
 *     Program
 *     Rate: 48000
 *     Decoder: MAT_DTHD decoder
 *     Stream: Third-party channel-based PCM
 *
 * Rows read from an entity's state, or from one of its attributes when
 * `attribute` is given - which is the whole reason this exists rather
 * than three picture-elements state-labels: sample rate and decoder are
 * ATTRIBUTES of sensor.tide16_stream, and one box here is far easier to
 * keep inside its cell than four separately-positioned labels.
 *
 * A value that is missing, unknown or unavailable prints as `placeholder`
 * ("-" by default), so a powered-down Tide16 reads "Decoder: -" instead
 * of a bare dangling "Decoder:". Rows carrying no `entity` are static
 * text and never get one.
 *
 * With no `rows` it degenerates to a single static line, which is how
 * the red MUTE flag is drawn - wrap it in a picture-elements
 * `conditional` to gate it on switch.tide16_mute.
 *
 * `title_image` puts a mark before the title text, which is how the
 * "Dolby Profiles" heading is drawn - the word "Dolby" is the double-D,
 * not type. The row is a baseline-aligned inline-flex, so the mark's
 * BOTTOM lands on the text's baseline, and `title_image_scale` is its
 * height in em: the 0.715 default is Roboto's cap height, so the mark
 * measures exactly as tall as the capital P beside it. Sizing it off the
 * em box instead would leave it floating, since a font's em box is
 * taller than its capitals.
 *
 * Positioning: give it left/top as usual, or set `right` and leave
 * `left: unset` and the width shrink-wraps the text, so the box's RIGHT
 * edge is what you positioned. That is what the mute flag needs - it is
 * pinned a fixed distance in from the screen's right edge, and "Mute"
 * must not drift depending on how wide the word renders.
 *
 * No font-family: inherits the frontend's, like every other readout.
 */

const READOUT_DEFAULTS = {
  title: null,
  title_color: '#808080', // the grey the plate's own "Source"/"Program" are printed in
  title_size: '0.805cqw', // measured off that same baked label
  title_gap: '0.15cqw',
  title_image: null, // a mark drawn before the title text
  title_image_scale: 0.715, // its height in em - Roboto's cap height
  title_image_gap: '0.3em',
  title_image_alt: null, // the word the mark stands in for
  color: '#B7B8B8',
  size: '0.45cqw',
  row_gap: '0.10cqw',
  align: 'left',
  placeholder: '-',
  // A value wider than its box scrolls rather than spilling across the plate.
  // Needs a WIDTH on the element in the YAML - without one the box shrink-wraps
  // the text and nothing can ever overflow it.
  scroll: false,
  scroll_speed: 14, // CSS px per second. The plate renders at about 0.67 CSS px
  // per canvas px, so this is a slow walk, not a ticker.
  rows: [],
  // A mark to the right of the rows, centred on them as a block, pulsing:
  //   badge: { image, size, min_opacity, period, hint, entity, state }
  // `period` is one fade, so a full dim-bright-dim cycle is twice it. With
  // `entity` it is drawn only while that entity reads `state` ("on").
  badge: null,
};

// Short month names for a `clock` row.  Written out rather than taken from
// Intl, which says "Sep" in the US and "Sept" in the UK - the panel always
// says "Sept".
const T16_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'];

class Tide16Readout extends HTMLElement {
  constructor() {
    super();
    this._cfg = { ...READOUT_DEFAULTS };
    this._hass = null;
    this._rowEls = [];
  }

  setConfig(config) {
    this._cfg = { ...READOUT_DEFAULTS, ...(config || {}) };
    if (!this._cfg.title && !this._cfg.rows.length) {
      throw new Error('tide16-readout: needs a `title`, `rows`, or both');
    }
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    this._paint();
  }

  // A `clock` row repaints itself on the minute; hass alone would only move it
  // when some state happened to change.
  connectedCallback() {
    if (!this._cfg.rows.some((r) => r.clock)) return;
    const tick = () => {
      this._paint();
      const now = new Date();
      this._tick = setTimeout(tick, 60000 - (now.getSeconds() * 1000 + now.getMilliseconds()) + 50);
    };
    clearTimeout(this._tick);
    tick();
  }

  disconnectedCallback() {
    clearTimeout(this._tick);
    this._tick = null;
  }

  /* A row in alert is drawn whole - label and value - in `alert_color` at
     `alert_weight`, and shows `alert_hint` on hover if it has one. Two things
     put a row in alert:

       alert_entity   that entity reads `alert_state` ("on")
       clock          the unit's own clock is more than `offset_max` seconds
                      from Home Assistant's, read from `offset_entity`

     `force_alert` holds it on, for seeing how it looks. */
  _rowAlarm(el, row) {
    let bad = !!row.force_alert;
    if (!bad && row.alert_entity && this._hass) {
      const st = this._hass.states[row.alert_entity];
      bad = !!st && st.state === (row.alert_state == null ? 'on' : String(row.alert_state));
    }
    if (!bad && row.clock) {
      const st = row.offset_entity && this._hass ? this._hass.states[row.offset_entity] : null;
      const off = st ? Number(st.state) : NaN;
      const max = row.offset_max == null ? 60 : Number(row.offset_max);
      bad = Number.isFinite(off) && Math.abs(off) > max;
    }
    // Only touched when it flips: this runs on every hass tick, and writing
    // the same styles over and over is wasted layout work.
    if (el.classList.contains('alarm') === bad && el.dataset.hint === (row.alert_hint || '')) return;
    el.classList.toggle('alarm', bad);
    el.dataset.hint = row.alert_hint || '';
    el.style.color = bad ? row.alert_color || '#8B0000' : '';
    el.style.fontWeight = bad ? row.alert_weight || 700 : '';
    if (this._tip) this._tip.textContent = bad ? row.alert_hint || '' : '';
  }

  /* "Sept 30, 00:26" - or "30 Sept, 00:26" where the country puts the day
     first. The time zone and country are the Home Assistant install's, not the
     browser's, so the plate reads the same from anywhere. */
  _clock() {
    const cfg = (this._hass && this._hass.config) || {};
    const now = new Date();
    const numeric = { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' };
    let parts;
    try {
      parts = new Intl.DateTimeFormat('en-US', { ...numeric, timeZone: cfg.time_zone }).formatToParts(now);
    } catch (e) {
      parts = new Intl.DateTimeFormat('en-US', numeric).formatToParts(now); // unknown zone
    }
    const p = Object.fromEntries(parts.map((x) => [x.type, x.value]));
    let dayFirst = false;
    try {
      const order = new Intl.DateTimeFormat('en-' + (cfg.country || 'US'), { month: 'short', day: 'numeric' })
        .formatToParts(now)
        .map((x) => x.type);
      dayFirst = order.indexOf('day') < order.indexOf('month');
    } catch (e) {
      /* unknown country: month first */
    }
    const month = T16_MONTHS[Number(p.month) - 1];
    const date = dayFirst ? `${p.day} ${month}` : `${month} ${p.day}`;
    return `${date}, ${p.hour}:${p.minute}`;
  }

  _build() {
    const c = this._cfg;
    const root = this.shadowRoot || this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        :host { display: block; position: absolute; pointer-events: none; }
        .block { text-align: ${c.align}; white-space: nowrap; }
        .wrap { display: flex; align-items: center; gap: ${(c.badge && c.badge.gap) || '0.4cqw'}; }
        .badge {
          flex: none;
          width: ${(c.badge && c.badge.size) || '1.659cqw'};
          height: ${(c.badge && c.badge.size) || '1.659cqw'};
          object-fit: contain;
          animation: t16-pulse ${(c.badge && c.badge.period) || 2}s ease-in-out infinite alternate;
        }
        @keyframes t16-pulse {
          from { opacity: ${c.badge && c.badge.min_opacity != null ? c.badge.min_opacity : 0.05}; }
          to { opacity: 1; }
        }
        .title {
          font-size: ${c.title_size};
          font-weight: 300;
          line-height: 1;
          color: ${c.title_color};
          padding-bottom: ${c.title_gap};
        }
        /* Block-level flex, NOT inline-flex: an inline-level heading is
           laid out on a line box, and the parent's own strut then adds
           leading above it, which pushed this heading 7.4px below the one
           it is meant to sit level with. Block-level starts flush at the
           top of the box, so the YAML's top offset means what it says.
           Block-level also means text-align no longer reaches it, hence
           justify-content off the same align option.
           NOTE: no backticks in here - this is inside a template literal
           and one would end the string. */
        .title.marked {
          display: flex;
          align-items: baseline;
          justify-content: ${
            c.align === 'right' ? 'flex-end' : c.align === 'center' ? 'center' : 'flex-start'
          };
          gap: ${c.title_image_gap};
        }
        .title .mark {
          flex: none;
          height: ${c.title_image_scale}em;
          width: auto;
        }
        .row {
          font-size: ${c.size};
          font-weight: 300;
          line-height: 1;
          color: ${c.color};
        }
        .row + .row { padding-top: ${c.row_gap}; }
        /* A clock row's warning. Drawn here rather than as a title attribute:
           hass repaints this several times a second while the meter runs, and
           the browser's own tooltip restarts on every repaint and never shows.
           It is a sibling after the rows, so hovering the row can reveal it,
           and it opens upward and leftward - the clock sits in the plate's
           bottom-right corner, where down or right would be clipped. */
        .row.alarm { pointer-events: auto; cursor: help; }
        .tip {
          display: none;
          position: absolute;
          right: 0;
          bottom: calc(100% + 0.4cqw);
          padding: 0.35cqw 0.6cqw;
          border-radius: 0.35cqw;
          background: rgba(20, 20, 20, 0.92);
          color: #fff;
          font-size: 0.85cqw;
          font-weight: 400;
          line-height: 1.2;
          white-space: nowrap;
          text-align: left;
          box-shadow: 0 0.15cqw 0.5cqw rgba(0, 0, 0, 0.35);
          pointer-events: none;
          z-index: 10;
        }
        .row.alarm:hover ~ .tip { display: block; }
        /* The badge's hint, the same way. A sibling rather than a child, so it
           does not pulse along with the badge. */
        .badge.hinted { pointer-events: auto; cursor: help; }
        .badge.hinted:hover ~ .tip { display: block; }
        /* Scrolling rows. The row is the window and .txt is the thing that
           moves, so the type never leaves the cell it belongs to. Held still at
           each end for a share of the cycle - a name you cannot read the start
           of is worse than one that does not move at all.
           NOTE: no backticks in here - this is inside a template literal and
           one would end the string. */
        .row.scroll { overflow: hidden; }
        .row.scroll .txt { display: inline-block; white-space: nowrap; }
        .row.scrolling .txt {
          animation: t16-scroll var(--t16-dur) ease-in-out infinite;
        }
        @keyframes t16-scroll {
          0%, 15% { transform: translateX(0); }
          50%, 65% { transform: translateX(calc(-1 * var(--t16-ov))); }
          100% { transform: translateX(0); }
        }
        @media (prefers-reduced-motion: reduce) {
          .row.scrolling .txt { animation: none; }
        }
      </style>
      <div class="wrap">
      <div class="block">
        ${c.title ? '<div class="title"></div>' : ''}
        ${c.rows
          .map(() =>
            c.scroll ? '<div class="row scroll"><span class="txt"></span></div>' : '<div class="row"></div>'
          )
          .join('')}
      </div>
      </div>`;

    if (c.badge && c.badge.image) {
      const b = document.createElement('img');
      b.className = 'badge';
      b.src = c.badge.image;
      b.alt = c.badge.alt == null ? '' : String(c.badge.alt);
      root.querySelector('.wrap').append(b);
      this._badge = b;
      if (c.badge.hint) {
        b.classList.add('hinted');
        const tip = document.createElement('div');
        tip.className = 'tip';
        tip.setAttribute('role', 'tooltip');
        tip.textContent = String(c.badge.hint);
        root.querySelector('.wrap').append(tip);
      }
    }

    // textContent rather than interpolation, so a label or a value that
    // happens to contain markup stays text
    if (c.title) {
      const t = root.querySelector('.title');
      if (c.title_image) {
        t.classList.add('marked');
        const mk = document.createElement('img');
        mk.className = 'mark';
        mk.src = c.title_image;
        // The mark stands in for a word, so it needs that word's name -
        // otherwise the heading reads as just "Profiles" to a screen
        // reader and to anyone whose images failed to load.
        mk.alt = c.title_image_alt == null ? '' : String(c.title_image_alt);
        const tx = document.createElement('span');
        tx.textContent = c.title;
        t.append(mk, tx);
      } else {
        t.textContent = c.title;
      }
    }
    this._rowEls = [...root.querySelectorAll('.row')];
    this._tip = null;
    if (c.rows.some((r) => r.alert_hint)) {
      this._tip = document.createElement('div');
      this._tip.className = 'tip';
      this._tip.setAttribute('role', 'tooltip');
      root.querySelector('.block').append(this._tip);
    }
    this._paint();

    // the plate scales with the window, so what fits changes with it
    if (c.scroll && !this._ro && typeof ResizeObserver !== 'undefined') {
      this._ro = new ResizeObserver(() => this._measure());
      this._ro.observe(this);
    }
  }

  _paint() {
    const c = this._cfg;
    if (this._badge && c.badge.entity) {
      const st = this._hass ? this._hass.states[c.badge.entity] : null;
      const shown = !!st && st.state === (c.badge.state == null ? 'on' : String(c.badge.state));
      // display, not visibility: hidden, it gives its space back and the rows
      // sit exactly where they would with no badge configured at all
      const want = shown ? '' : 'none';
      if (this._badge.style.display !== want) this._badge.style.display = want;
    }
    if (!this._rowEls.length) return;
    let changed = false;
    c.rows.forEach((r, i) => {
      const el = this._rowEls[i];
      if (!el) return;
      if (r.clock || r.alert_entity) this._rowAlarm(el, r);
      const value = this._value(r);
      const text = [r.label, value].filter(Boolean).join(' ');
      // .txt is the span that moves when the row scrolls; without scrolling the
      // row itself holds the text, exactly as before
      const target = c.scroll ? el.firstElementChild : el;
      if (target.textContent === text) return;
      target.textContent = text;
      changed = true;
    });
    // hass ticks at 4 Hz while the meter is on screen, and measuring forces
    // layout - so only remeasure when a value actually changed
    if (c.scroll && changed) this._measure();
  }

  /* Does any row overflow its cell, and by how much? Sets the animation up per
     row, since one block can hold a short line and a long one.

     Deliberately measured rather than guessed from character counts: the panel
     inherits the frontend's font, so the same string is a different width on a
     different machine. */
  _measure() {
    const c = this._cfg;
    if (this._raf) cancelAnimationFrame(this._raf);
    // after layout, or scrollWidth is read against the previous text
    this._raf = requestAnimationFrame(() => {
      this._raf = null;
      this._rowEls.forEach((el) => {
        const txt = el.firstElementChild;
        if (!txt) return;
        const over = txt.scrollWidth - el.clientWidth;
        if (over > 0.5) {
          // travel is 35% of the cycle each way, so the rest is the pause at
          // either end and the speed stays what scroll_speed says
          const dur = over / (Number(c.scroll_speed) * 0.35);
          el.style.setProperty('--t16-ov', over + 'px');
          el.style.setProperty('--t16-dur', dur.toFixed(2) + 's');
          el.classList.add('scrolling');
        } else {
          el.classList.remove('scrolling');
          el.style.removeProperty('--t16-ov');
          el.style.removeProperty('--t16-dur');
        }
      });
    });
  }

  /* Every way a value can be absent lands on `placeholder`: no hass yet,
     no such entity, no such attribute, or a state of unknown/unavailable.
     That matters on a cold start - for ~15s after a restart these
     entities do not exist at all, and for ~12s after that they read
     `unknown`. A built-in state-label prints that word; this prints "-"
     from the very first paint.

     `prefix` is applied ONLY to a real value. The volume's decimal half
     uses it for the point, so a missing reading draws nothing rather
     than a stray ".". */
  _value(row) {
    if (row.clock) return this._clock();
    // A row with no entity is static text - it has nothing to be missing.
    if (!row.entity) return '';
    const gone = row.placeholder == null ? this._cfg.placeholder : row.placeholder;
    if (!this._hass) return gone;
    const st = this._hass.states[row.entity];
    if (!st) return gone;
    const v = row.attribute ? st.attributes[row.attribute] : st.state;
    if (v === undefined || v === null || v === '') return gone;
    if (['unknown', 'unavailable'].includes(String(v))) return gone;
    return (row.prefix == null ? '' : String(row.prefix)) + String(v);
  }

  getCardSize() {
    return 1;
  }
}

if (!customElements.get('tide16-readout')) {
  customElements.define('tide16-readout', Tide16Readout);
}

/* =====================================================================
 * tide16-inputs - a grid of dot-and-label source selectors.
 *
 * Each cell is a small round button followed by its input name, laid out
 * as `columns` x `rows` across whatever box the YAML gives it. Flow is
 * grid-auto-flow: column, so the items fill DOWN each column and then
 * move right - which is what keeps an alphabetical list reading in order
 * when it is arranged as columns of two rather than rows of six.
 *
 * The box IS the geometry: the grid fills it at 100% x 100% and the rows
 * are 1fr each, so the row height is whatever is left after `row_gap`.
 * Re-positioning or resizing the box can only change spacing.
 *
 * The whole cell is the hit target, not just the dot - a 13px circle is
 * a mean thing to ask anyone to hit, and the label is right there.
 *
 * Each item is {text, id?, tap?, hint?} with the same {action, data} shape the
 * rest of the card uses. A tappable cell gets hover text - "Select
 * source: Roku" unless `hint` says otherwise. Sources are selected through
 * media_player.select_source rather than the button.tide16_source_*
 * entities: those are named after the physical inputs (hdmi_2, spotify)
 * while the device reports the user's RENAMED sources ("Roku",
 * "Comcast"), so the names in source_list are the only thing that maps
 * one-to-one with what the panel actually displays.
 *
 * box-sizing: border-box on the dot on purpose - the border must not
 * grow it, or the circle stops matching the size the YAML asked for.
 *
 * NOTE for the YAML: quote the `border` value. Unquoted, YAML reads
 * "#666666" as a comment and hands over a bare "1px solid", which CSS
 * completes with currentColor - a white border, silently.
 *
 * No font-family: inherits the frontend's, like every other readout.
 */

const INPUT_DEFAULTS = {
  columns: 6,
  rows: 2,
  row_gap: '0.503cqw', // 10px of the 1990 canvas
  dot: '0.653cqw', // diameter of the round button
  dot_gap: '0.302cqw', // between the button and its label
  size: '0.704cqw',
  // 400 is the source rows' own weight. The Dolby column sets 300 to
  // match the plate's headings: at an IDENTICAL font-size, 400 against
  // the heading's 300 reads as a bigger label, not just a heavier one -
  // which is why matching only the size looked like nothing had changed.
  weight: '400',
  color: '#B7B8B8',
  // the live source is read off an entity attribute and matched against
  // each item's text (or its `value`, if the label differs from what the
  // device reports), so the panel shows which input is actually selected
  active_entity: null,
  active_attribute: 'source',
  active_color: '#FFFFFF',
  // the live source can also be set a notch larger than the rest; null
  // leaves it at `size`. Cells are align-items: center, so a taller label
  // grows about the row's middle and cannot shift the row it sits in.
  active_size: null,
  // ...or heavier instead of larger, which is what the Dolby column uses:
  // its rows have to stay level with the scene bars beside them, and
  // weight marks the selection without touching the type size at all.
  active_weight: null,
  background: '#333333',
  border: '1px solid #666666',
  // The live one's button, so the selection reads at a glance from the
  // dot alone rather than only from the label's weight. null on either
  // leaves the inactive styling in place.
  // box-sizing on .dot is border-box, so a heavier active border cannot
  // grow the circle out of register with the rest of the column.
  active_background: null,
  active_border: null,
  // Which inputs are actually CONFIGURED, read live off the device. The map is
  // {id: {name, hidden}} exactly as the Tide16's get_settings -> sources gives
  // it (see scripts/tide16_sources.py, surfaced as a command_line sensor).
  // Items opt in by carrying an `id`. A hidden input is still drawn - the panel
  // has twelve inputs and always will - but pushed back and made inert.
  source_entity: null,
  source_attribute: 'sources',
  // pushed well back rather than merely dimmed: the point is that the three
  // configured inputs are what the eye lands on first
  disabled_color: '#5E5F5F',
  disabled_background: '#1F1F1F',
  disabled_border: '1px solid #3A3A3A',
  items: [],
};

class Tide16Inputs extends HTMLElement {
  constructor() {
    super();
    this._cfg = { ...INPUT_DEFAULTS };
    this._hass = null;
  }

  setConfig(config) {
    this._cfg = { ...INPUT_DEFAULTS, ...(config || {}) };
    if (!Array.isArray(this._cfg.items) || !this._cfg.items.length) {
      throw new Error('tide16-inputs: `items` must be a non-empty list');
    }
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    this._paintSources();
    this._paintActive();
  }

  /* Which inputs are configured? The device's own hidden flag decides, so the
     panel follows whatever is set in the Tide16's UI without a card edit.
     Matching is by `id`, which also keeps every label in step with whatever the
     input has been RENAMED to - the YAML `text` is only the fallback for when
     the map is missing.

     Fail-open on purpose: an absent or empty map leaves every cell selectable.
     The map arrives from a polled command_line sensor, and a sensor that dies
     must not be able to render the whole input row inert. */
  _paintSources() {
    const c = this._cfg;
    if (!this._hass || !c.source_entity || !this._cells) return;
    const st = this._hass.states[c.source_entity];
    const map = st && c.source_attribute ? st.attributes[c.source_attribute] : null;
    if (!map || typeof map !== 'object' || !Object.keys(map).length) return;

    // hass ticks at 4 Hz while the meter is on screen and this table changes
    // about never, so repaint only when it actually differs
    const stamp = JSON.stringify(map);
    if (stamp === this._sourceStamp) return;
    this._sourceStamp = stamp;

    this._cells.forEach((cell) => {
      const it = cell._item;
      const entry = it && it.id != null ? map[it.id] : null;
      if (!entry) return;

      if (entry.name) {
        cell._lbl.textContent = String(entry.name);
        // select_source takes the DISPLAY name, so a renamed input needs the
        // new name in the payload or the tap quietly selects nothing. Held on
        // the CELL and merged in at fire time - Lovelace deep-freezes the
        // config it hands over, so writing it.tap.data.source throws
        // "Cannot assign to read only property", and a throw in this setter
        // takes the whole card's render down with it (card-mod stops applying,
        // and the plate loses its scale/outline box).
        cell._source = String(entry.name);
        if (it.hint == null && it.tap && it.tap.action) {
          cell.title = `Select source: ${entry.name}`;
        }
      }

      const hidden = entry.hidden === true;
      cell.classList.toggle('unconfigured', hidden);
      if (hidden) {
        // no pointer, no hover text, no press feedback - an inert cell must not
        // advertise itself as tappable
        delete cell.dataset.tap;
        cell.removeAttribute('title');
      } else if (it.tap && it.tap.action) {
        cell.dataset.tap = '';
      }
    });

    // a rename can move which label is the live one
    this._active = undefined;
    this._paintActive();
  }

  /* Which item is the live source? Repainted on every hass update, but
     only touched when the value actually changes - hass ticks at 4 Hz
     while the meter is on screen. */
  _paintActive() {
    const c = this._cfg;
    if (!this._hass || !c.active_entity || !this._cells) return;
    const st = this._hass.states[c.active_entity];
    const cur = st
      ? c.active_attribute
        ? st.attributes[c.active_attribute]
        : st.state
      : null;
    if (cur === this._active) return;
    this._active = cur;
    this._cells.forEach((cell, i) => {
      const it = c.items[i];
      // A renamed input reports its NEW name as the live source, so the name
      // read off the device (cell._source, set in _paintSources) is what has
      // to match - the YAML text/value is only the fallback without a map.
      const want = cell._source != null ? cell._source : it.value == null ? it.text : it.value;
      cell.classList.toggle('on', cur != null && String(want) === String(cur));
    });
  }

  _build() {
    const c = this._cfg;
    const root = this.shadowRoot || this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        :host { display: block; position: absolute; }
        .grid {
          display: grid;
          grid-template-columns: repeat(${c.columns}, 1fr);
          grid-template-rows: repeat(${c.rows}, 1fr);
          /* fill down each column, then move right */
          grid-auto-flow: column;
          row-gap: ${c.row_gap};
          width: 100%;
          height: 100%;
        }
        .cell {
          display: flex;
          align-items: center;
          gap: ${c.dot_gap};
          white-space: nowrap;
          user-select: none;
          /* Grid items default to min-height: auto, so a cell taller than
             its 1fr track grows the track instead of overflowing it, and
             the rows walk off whatever the box was aligned to. The Dolby
             column is exactly that case - 20px dot and 21px type in an
             18.3px track - and without this its rows drift up to 12px
             clear of the scene bars they are supposed to sit level with.
             At 0 the track stays 1fr and the content overflows centred,
             so the row's midline is the track's midline. No effect on the
             source grid, whose type is shorter than its rows. */
          min-height: 0;
        }
        .dot {
          box-sizing: border-box;
          flex: none;
          width: ${c.dot};
          height: ${c.dot};
          border-radius: 50%;
          background: ${c.background};
          border: ${c.border};
        }
        .lbl {
          font-size: ${c.size};
          font-weight: ${c.weight};
          line-height: 1;
          letter-spacing: 0.03em;
          color: ${c.color};
        }
        .cell[data-tap] { cursor: pointer; }
        .cell[data-tap]:active .dot { filter: brightness(1.9); }
        .cell[data-tap]:active .lbl { opacity: 0.6; }
        /* the input the device is actually on */
        .cell.on .dot {
          ${c.active_background ? `background: ${c.active_background};` : ''}
          ${c.active_border ? `border: ${c.active_border};` : ''}
        }
        .cell.on .lbl {
          color: ${c.active_color};
          ${c.active_size ? `font-size: ${c.active_size};` : ''}
          ${c.active_weight ? `font-weight: ${c.active_weight};` : ''}
          text-decoration: underline;
          text-underline-offset: 0.22em;
          text-decoration-thickness: from-font;
        }
        /* an input the device has hidden: still drawn, but pushed back so the
           configured ones stand out, and inert. Declared after .cell.on so a
           hidden input could never be painted as the live one. */
        .cell.unconfigured { cursor: default; }
        .cell.unconfigured .lbl {
          color: ${c.disabled_color};
          text-decoration: none;
        }
        .cell.unconfigured .dot {
          background: ${c.disabled_background};
          border: ${c.disabled_border};
        }
      </style>
      <div class="grid"></div>`;

    this._cells = [];
    const grid = root.querySelector('.grid');
    c.items.forEach((it) => {
      const cell = document.createElement('div');
      cell.className = 'cell';
      const dot = document.createElement('span');
      dot.className = 'dot';
      const lbl = document.createElement('span');
      lbl.className = 'lbl';
      // textContent, not interpolation, so a source name containing
      // markup stays text
      lbl.textContent = it.text == null ? '' : String(it.text);
      cell.appendChild(dot);
      cell.appendChild(lbl);
      // kept for _paintSources: it relabels cells and flips them inert
      cell._lbl = lbl;
      cell._item = it;
      if (it.tap && it.tap.action) {
        cell.dataset.tap = '';
        // guarded at fire time rather than at build time - `unconfigured` is
        // painted from live device state and can flip either way without a
        // rebuild, and a removed data-tap only changes the cursor
        cell.addEventListener('click', () => {
          if (cell.classList.contains('unconfigured')) return;
          this._fire(it.tap, cell._source);
        });
        // hover text says what the click does. Only the tappable cells
        // get one - a tooltip on something inert is a lie.
        cell.title = it.hint == null ? `Select source: ${lbl.textContent}` : String(it.hint);
      } else if (it.hint != null) {
        cell.title = String(it.hint);
      }
      this._cells.push(cell);
      grid.appendChild(cell);
    });
    this._active = undefined;
    this._sourceStamp = undefined;
    this._paintActive();
    this._paintSources();
  }

  /* `source` is the live name for this cell, if the device reported one.
     Merged into a COPY of the config's data - the config itself is frozen. */
  _fire(tap, source) {
    if (!this._hass) return;
    const [domain, service] = String(tap.action).split('.');
    if (!domain || !service) return;
    const data = { ...(tap.data || {}) };
    if (source && 'source' in data) data.source = source;
    this._hass.callService(domain, service, data);
  }

  getCardSize() {
    return 1;
  }
}

if (!customElements.get('tide16-inputs')) {
  customElements.define('tide16-inputs', Tide16Inputs);
}

/* =====================================================================
 * tide16-select - the panel's one drop-down, drawn as a raised button.
 *
 * Reads a `select` entity: its state is the current option and its
 * `options` attribute is the list. Tapping the button opens that list
 * below it; picking a row calls select.select_option.
 *
 * WHY A BUTTON AND NOT A <select>: the plate is hardware, and a native
 * control is the one thing on it that would look like a web page. So the
 * face is a cap milled proud of the panel - the exact inverse of the
 * concave dish tide16-glyph draws for Reboot, and lit the opposite way
 * round: bright at the TOP, with a skirt under it and a shadow on the
 * plate. It stays PRESSED for as long as the list is open, so the panel
 * always says whether it is waiting for an answer.
 *
 * THE LABEL IS TWO FIELDS, not one string. Every preset slot on this
 * hardware reports an empty name, so today the options are bare ids and
 * the face reads "1:". A named slot arrives as "1: Atmos" and the number
 * still has to stay put and stay legible - so the id is drawn fixed and
 * the NAME is the part that scrolls when it will not fit. Splitting on
 * the first colon is what the integration's preset_label builds, and the
 * two halves are styled separately here.
 *
 * WHY THE LIST IS PORTALLED TO document.body: the plate is clipped. The
 * card's wrapper sets container-type: inline-size (every font on the
 * panel is sized in cqw), and container-type implies layout containment,
 * which makes that wrapper the containing block for FIXED descendants
 * too - so position: fixed does not escape its overflow: hidden the way
 * it normally would. Inside the plate there are about 55 canvas px below
 * this button before the artwork ends: one row. The list therefore lives
 * outside the card entirely, in its own shadow root so the dashboard's
 * CSS cannot reach it, positioned from the button's own rect and moved
 * with it on scroll and resize.
 *
 * The list is sized in PIXELS, not cqw: outside the card there is no
 * container for cqw to resolve against. The face's computed font-size is
 * read back and the rows are built from it, so the two match at any card
 * width.
 *
 * No font-family: inherits the frontend's, like every other readout.
 */

const SELECT_DEFAULTS = {
  entity: null,
  // drawn ABOVE the box in the plate's heading style, so the YAML box is
  // exactly the button - same rule the rest of the card follows
  title: null,
  // The heading and the face both read at the size the Dolby Profiles and
  // Modes columns beside them use, so the three controls in the plate's
  // right-hand void are one family rather than three.
  title_size: '1.070cqw',
  title_color: '#BFC0C0',
  title_gap: '0.16cqw',
  size: '1.070cqw',
  weight: '700',
  color: '#FFFFFF',
  radius: '0.28cqw',
  // how far the cap stands off the plate. The box holds cap AND skirt, so
  // raising this shortens the face rather than growing the element.
  lift: '0.40cqw',
  border: '#3f434a', // the base edge; each side is then lit for itself
  border_hover: '#a3a8b1',
  // rows visible before the list scrolls; the viewport can cut it shorter
  menu_rows: 6,
  menu_color: '#B7B8B8',
  menu_active_color: '#FFFFFF',
  scroll_speed: 14, // CSS px/s, as in tide16-readout
  placeholder: '-',
  hint: null,
};

// Row height and padding as multiples of the face's own font-size, so the
// list stays in proportion however wide the card is drawn.
const MENU_ROW_EM = 2.1;
const MENU_PAD_EM = 0.8;
const MENU_GAP_PX = 4; // between the button and the list it drops

/* "1: Atmos" -> {num: "1", name: "Atmos"}; "1" -> {num: "1", name: ""}.
   Split on the FIRST colon only - a preset could well be named "Movie: 5.1"
   and the id is only ever the leading field. */
function splitOption(option) {
  const s = option == null ? '' : String(option);
  const i = s.indexOf(':');
  if (i < 0) return { num: s.trim(), name: '' };
  return { num: s.slice(0, i).trim(), name: s.slice(i + 1).trim() };
}

class Tide16Select extends HTMLElement {
  constructor() {
    super();
    this._cfg = { ...SELECT_DEFAULTS };
    this._hass = null;
    this._open = false;
    this._options = [];
    this._current = null;
  }

  setConfig(config) {
    this._cfg = { ...SELECT_DEFAULTS, ...(config || {}) };
    if (!this._cfg.entity) {
      throw new Error('tide16-select: needs an `entity`');
    }
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    this._paint();
  }

  disconnectedCallback() {
    // A view switch removes the card but not a node parented on document.body
    this._close();
  }

  _build() {
    const c = this._cfg;
    const root = this.shadowRoot || this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        :host { display: block; position: absolute; }
        /* The heading hangs above the box rather than sitting inside it, so
           the box the YAML measures IS the button - re-positioning the
           element can only move the pair, never resize the face. */
        .title {
          position: absolute;
          left: 0;
          right: 0;
          bottom: calc(100% + ${c.title_gap});
          text-align: center;
          white-space: nowrap;
          font-size: ${c.title_size};
          font-weight: 300;
          line-height: 1;
          color: ${c.title_color};
          pointer-events: none;
        }
        /* A cap standing proud of the panel, lit from the RIGHT.
           
           The angle is not a choice - it is measured off plate-v3. The
           standby knob beside this button is baked into the art and its
           light comes in horizontally from the right: its specular rim peaks
           at 0deg (222 luma against a 147 body) and its face falls away to
           16 at 180deg. A cap lit from the top next to a knob lit from the
           right is two light sources on one panel, which is the one thing
           photoreal artwork cannot survive.
           
           So: bright along the right edge, falling to near-black at the
           left, with a specular strip down the right the way the knob
           carries one round its rim. The hard un-blurred offset beneath is
           the SKIRT, the side wall of the button - that is viewpoint, not
           light, and it stays put; the blurred shadow is what the cap throws
           on the plate, and with the light on the right that falls to the
           LEFT. The box holds cap and skirt both, so the face stops one lift
           short of the bottom edge. */
        .cap {
          position: absolute;
          left: 0;
          right: 0;
          top: 0;
          bottom: ${c.lift};
          box-sizing: border-box;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.34em;
          overflow: hidden;
          border-radius: ${c.radius};
          /* Three different edges, because they are three different surfaces:
             the top catches the light, the sides are in half shadow, and the
             bottom is the underside of the cap where the skirt begins. A
             single uniform border draws all four the same and the cap goes
             flat however strong the gradient behind it is. */
          border: 1px solid ${c.border};
          /* the edge facing the light, and the one hiding from it */
          border-right-color: #7a8089;
          border-left-color: #0c0e11;
          border-top-color: #4b5058;
          border-bottom-color: #15181c;
          background:
            /* the top and bottom of the cap rolling away, drawn over... */
            linear-gradient(180deg, rgba(255,255,255,0.05) 0%, rgba(0,0,0,0) 20%,
                            rgba(0,0,0,0) 76%, rgba(0,0,0,0.28) 100%),
            /* ...the face itself, lit from the right, on the knob's own ramp:
               a bright flank at 0deg falling to near-black at 180deg. */
            linear-gradient(270deg, #565b62 0%, #464a50 18%, #33363b 52%,
                            #212429 82%, #17191c 100%);
          box-shadow:
            /* the specular down the right edge - the knob's rim reads 222
               against its own 147 face, so the cap gets one too */
            inset -1px 0 0 rgba(255, 255, 255, 0.40),
            inset -4px 0 5px -3px rgba(255, 255, 255, 0.16),
            /* the left flank, curling away into the dark */
            inset 3px 0 5px -2px rgba(0, 0, 0, 0.85),
            /* the side wall the cap stands on - a hard, UNBLURRED offset, so
               it reads as a wall and not as another shadow - and then the
               shadow it throws on the plate, thrown LEFT because that is
               where a light on the right puts it */
            0 ${c.lift} 0 -1px #0b0d10,
            -4px calc(${c.lift} + 1px) 6px rgba(0, 0, 0, 0.9);
          font-size: ${c.size};
          font-weight: ${c.weight};
          line-height: 1;
          color: ${c.color};
          letter-spacing: 0.02em;
          user-select: none;
          cursor: pointer;
          transition: transform 70ms ease-out, box-shadow 70ms ease-out;
        }
        .cap:hover { border-color: ${c.border_hover}; }
        .cap:focus-visible { outline: 1px solid ${c.border_hover}; outline-offset: 1px; }
        /* Pressed, and it STAYS pressed while the list is open: the cap sits
           down on its skirt, the skirt is gone, and the face darkens under
           the rim's shadow. */
        /* Pressed, and the light does not move with it: the face has sunk
           into the panel, so the rim on the RIGHT now stands between it and
           the light and throws a shadow across it, while what light still
           reaches the recess lands on the far LEFT wall. The bright flank
           swapping sides is the whole cue - exactly the inversion the Reboot
           dish uses, turned through the same 90 degrees as everything else
           here. */
        .cap.down {
          transform: translateY(${c.lift});
          border-right-color: #0c0e11;
          border-left-color: #3a3e44;
          border-top-color: #16191d;
          background: linear-gradient(90deg, #2c3035 0%, #212428 42%, #15171a 100%);
          box-shadow:
            inset -4px 0 6px -2px rgba(0, 0, 0, 0.95),
            inset 1px 0 0 rgba(255, 255, 255, 0.10),
            -1px 1px 2px rgba(0, 0, 0, 0.6);
        }
        .cap.down .num, .cap.down .name { opacity: 0.82; }
        /* Nothing to choose from: no pointer, no press, pushed back - the
           same treatment a hidden input gets in tide16-inputs. */
        .cap.dead {
          cursor: default;
          color: #5E5F5F;
          border-color: #3A3A3A;
        }
        .num { flex: none; }
        /* The name is the half that gives: it shrinks to whatever the cap has
           left and scrolls inside that, so the number can never be pushed off
           the button by a long one. min-width: 0 is what lets a nowrap child
           shrink below its own content at all. */
        .name { flex: 0 1 auto; min-width: 0; overflow: hidden; }
        .name.empty { display: none; }
        .name .txt { display: inline-block; white-space: nowrap; }
        .name.scrolling .txt {
          animation: t16-sel-scroll var(--t16-dur) ease-in-out infinite;
        }
        @keyframes t16-sel-scroll {
          0%, 15% { transform: translateX(0); }
          50%, 65% { transform: translateX(calc(-1 * var(--t16-ov))); }
          100% { transform: translateX(0); }
        }
        @media (prefers-reduced-motion: reduce) {
          .name.scrolling .txt { animation: none; }
        }
      </style>
      ${c.title ? '<div class="title"></div>' : ''}
      <div class="cap" role="button" tabindex="0" aria-haspopup="listbox" aria-expanded="false">
        <span class="num"></span><span class="name"><span class="txt"></span></span>
      </div>`;

    if (c.title) root.querySelector('.title').textContent = c.title;
    this._cap = root.querySelector('.cap');
    this._num = root.querySelector('.num');
    this._nameBox = root.querySelector('.name');
    this._nameTxt = root.querySelector('.name .txt');
    if (c.hint) this._cap.title = String(c.hint);

    this._cap.addEventListener('click', () => this._toggle());
    this._cap.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        this._toggle();
      } else if (ev.key === 'ArrowDown' && !this._open) {
        ev.preventDefault();
        this._toggle();
      }
    });

    // the plate scales with the window, so what fits on the cap changes too
    if (!this._ro && typeof ResizeObserver !== 'undefined') {
      this._ro = new ResizeObserver(() => {
        this._measure();
        if (this._open) this._place();
      });
      this._ro.observe(this);
    }
    this._paint();
  }

  /* The entity in one shape: the list, the live one, and whether there is
     anything to choose at all. Everything downstream reads this.

     `unknown` is NOT dead. The unit can be up and answering with the panel
     still not knowing which slot is live - a reconnect before the index has
     come back does exactly that - and a button that will not open because a
     readout has not landed yet is a button that looks broken. Only an
     unavailable entity, or one with nothing to choose, goes inert. */
  _read() {
    const c = this._cfg;
    const st = this._hass ? this._hass.states[c.entity] : null;
    const value = st ? String(st.state) : 'unavailable';
    const live = !!st && value !== 'unavailable';
    const options = live && Array.isArray(st.attributes.options) ? st.attributes.options : [];
    return {
      dead: !live || !options.length,
      options,
      current: live && value !== 'unknown' ? value : null,
    };
  }

  _paint() {
    const c = this._cfg;
    if (!this._cap) return;
    const { dead, options, current } = this._read();

    this._options = options;
    this._current = current;
    this._cap.classList.toggle('dead', dead);

    const { num, name } = current == null ? { num: '', name: '' } : splitOption(current);
    // The colon belongs to the panel, not to the option string: an unnamed
    // slot arrives as a bare "1" and still has to read "1:" on the face.
    const numText = num ? `${num}:` : c.placeholder;
    let changed = false;
    if (this._num.textContent !== numText) {
      this._num.textContent = numText;
      changed = true;
    }
    if (this._nameTxt.textContent !== name) {
      this._nameTxt.textContent = name;
      this._nameBox.classList.toggle('empty', !name);
      changed = true;
    }
    // hass ticks at 4 Hz while the meter is on screen and measuring forces
    // layout, so only remeasure when the text actually moved
    if (changed) this._measure();
    if (this._open) this._paintMenu();
  }

  /* Does the name overflow the cap, and by how much? Measured rather than
     guessed from character counts - the panel inherits the frontend's font,
     so the same name is a different width on a different machine. */
  _measure() {
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = requestAnimationFrame(() => {
      this._raf = null;
      const box = this._nameBox;
      const txt = this._nameTxt;
      if (!box || !txt) return;
      const over = txt.scrollWidth - box.clientWidth;
      if (over > 0.5) {
        // travel is 35% of the cycle each way; the rest is the pause at
        // either end, so scroll_speed stays the speed it says
        const dur = over / (Number(this._cfg.scroll_speed) * 0.35);
        box.style.setProperty('--t16-ov', `${over}px`);
        box.style.setProperty('--t16-dur', `${dur.toFixed(2)}s`);
        box.classList.add('scrolling');
      } else {
        box.classList.remove('scrolling');
        box.style.removeProperty('--t16-ov');
        box.style.removeProperty('--t16-dur');
      }
    });
  }

  _toggle() {
    if (this._open) this._close();
    else this._openMenu();
  }

  _openMenu() {
    const { dead, options } = this._read();
    if (dead || !options.length) return;

    const host = document.createElement('div');
    host.style.cssText = 'position:fixed;z-index:9999;left:0;top:0;';
    const root = host.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        .menu {
          position: fixed;
          box-sizing: border-box;
          overflow-y: auto;
          overscroll-behavior: contain;
          border-radius: 4px;
          border: 1px solid #4a4d53;
          background: #17191c;
          box-shadow: 0 6px 16px rgba(0, 0, 0, 0.75);
          padding: 3px 0;
        }
        .row {
          display: flex;
          align-items: center;
          gap: 0.34em;
          white-space: nowrap;
          overflow: hidden;
          line-height: 1;
          color: ${this._cfg.menu_color};
          cursor: pointer;
        }
        .row:hover, .row:focus-visible { background: #2b2e33; outline: none; }
        .row.on {
          color: ${this._cfg.menu_active_color};
          font-weight: 700;
        }
        .row .num { flex: none; }
        .row .name { overflow: hidden; text-overflow: ellipsis; }
        /* Nothing but numbers to show - which is every preset on this
           firmware - and a left-aligned column of "1:" under a centred face
           reads as a mistake. Named slots go back to left-aligned, because
           that is what a list of words is scanned down. */
        .menu.numbers .row { justify-content: center; }
      </style>
      <div class="menu" role="listbox" tabindex="-1"></div>`;
    document.body.appendChild(host);
    this._menuHost = host;
    this._menu = root.querySelector('.menu');

    this._menu.addEventListener('keydown', (ev) => this._menuKey(ev));
    this._open = true;
    this._cap.classList.add('down');
    this._cap.setAttribute('aria-expanded', 'true');
    this._paintMenu();
    this._place();

    // pointerdown, not click: a click that lands on the plate would otherwise
    // fire the element under it as well as closing this
    this._onDown = (ev) => {
      const path = ev.composedPath();
      if (path.includes(this._menuHost) || path.includes(this._cap)) return;
      this._close();
    };
    this._onKey = (ev) => {
      if (ev.key === 'Escape') {
        this._close();
        this._cap.focus();
      }
    };
    // capture, so a scroller anywhere in the page - a dialog, a sub-view -
    // moves the list with the button instead of leaving it stranded
    this._onMove = () => this._place();
    document.addEventListener('pointerdown', this._onDown, true);
    document.addEventListener('keydown', this._onKey, true);
    window.addEventListener('scroll', this._onMove, true);
    window.addEventListener('resize', this._onMove);

    const live = this._menu.querySelector('.row.on') || this._menu.firstElementChild;
    if (live) live.focus();
  }

  _paintMenu() {
    if (!this._menu) return;
    const stamp = JSON.stringify([this._options, this._current]);
    if (stamp === this._menuStamp) return;
    this._menuStamp = stamp;

    this._menu.textContent = '';
    this._options.forEach((option) => {
      const { num, name } = splitOption(option);
      const row = document.createElement('div');
      row.className = 'row';
      row.setAttribute('role', 'option');
      row.tabIndex = -1;
      const on = String(option) === String(this._current);
      row.classList.toggle('on', on);
      row.setAttribute('aria-selected', on ? 'true' : 'false');
      const n = document.createElement('span');
      n.className = 'num';
      n.textContent = num ? `${num}:` : '';
      const t = document.createElement('span');
      t.className = 'name';
      // textContent, not interpolation, so a preset named with markup in it
      // stays text
      t.textContent = name;
      row.append(n, t);
      row.addEventListener('click', () => this._pick(option));
      this._menu.appendChild(row);
    });
    this._menu.classList.toggle(
      'numbers',
      this._options.every((o) => !splitOption(o).name)
    );
    // rows exist now, so their height is known
    if (this._open) this._place();
  }

  /* Put the list under the button, in viewport coordinates read off the
     button itself. Sized in px off the cap's own computed font-size, since
     cqw has no container to resolve against out here. */
  _place() {
    if (!this._menu || !this._cap) return;
    const r = this._cap.getBoundingClientRect();
    const fs = parseFloat(getComputedStyle(this._cap).fontSize) || 14;
    const rowH = fs * MENU_ROW_EM;
    const pad = fs * MENU_PAD_EM;

    const m = this._menu;
    m.style.fontSize = `${fs}px`;
    m.style.minWidth = `${r.width}px`;
    m.style.maxWidth = `${Math.min(r.width * 2.4, window.innerWidth - 16)}px`;
    [...m.children].forEach((row) => {
      row.style.height = `${rowH}px`;
      row.style.padding = `0 ${pad}px`;
    });

    // The button is pressed and the list drops from under it, which is the
    // gesture the panel promises. Below is the default and stays the default
    // even when it has to scroll; it only flips when below cannot hold two
    // rows AND above can hold more - a list you have to scroll is workable,
    // one clipped to half a row is not.
    const below = window.innerHeight - r.bottom - MENU_GAP_PX - 8;
    const above = r.top - MENU_GAP_PX - 8;
    const wanted = this._options.length * rowH + 6;
    const up = below < rowH * 2 && above > below;
    const cap = Math.min(wanted, this._cfg.menu_rows * rowH + 6, up ? above : below);

    m.style.maxHeight = `${Math.max(rowH, cap)}px`;
    m.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - r.width - 8))}px`;
    if (up) {
      m.style.top = 'auto';
      m.style.bottom = `${window.innerHeight - r.top + MENU_GAP_PX}px`;
    } else {
      m.style.bottom = 'auto';
      m.style.top = `${r.bottom + MENU_GAP_PX}px`;
    }
  }

  _menuKey(ev) {
    const rows = [...this._menu.children];
    const i = rows.indexOf(this._menu.getRootNode().activeElement);
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      ev.preventDefault();
      const next = ev.key === 'ArrowDown' ? i + 1 : i - 1;
      const el = rows[(next + rows.length) % rows.length];
      if (el) el.focus();
    } else if (ev.key === 'Enter' || ev.key === ' ') {
      ev.preventDefault();
      if (rows[i]) rows[i].click();
    }
  }

  _pick(option) {
    this._close();
    if (!this._hass) return;
    this._hass.callService('select', 'select_option', {
      entity_id: this._cfg.entity,
      option,
    });
  }

  _close() {
    this._open = false;
    this._menuStamp = undefined;
    if (this._cap) {
      this._cap.classList.remove('down');
      this._cap.setAttribute('aria-expanded', 'false');
    }
    if (this._menuHost) {
      this._menuHost.remove();
      this._menuHost = null;
      this._menu = null;
    }
    if (this._onDown) document.removeEventListener('pointerdown', this._onDown, true);
    if (this._onKey) document.removeEventListener('keydown', this._onKey, true);
    if (this._onMove) {
      window.removeEventListener('scroll', this._onMove, true);
      window.removeEventListener('resize', this._onMove);
    }
    this._onDown = this._onKey = this._onMove = null;
  }

  getCardSize() {
    return 1;
  }
}

if (!customElements.get('tide16-select')) {
  customElements.define('tide16-select', Tide16Select);
}


/**
 * tide16-panel - the whole front panel, as ONE card.
 *
 * The nine elements above are picture-elements *elements*: each one needs a
 * box measured off the plate, and wiring them by hand is the 1000-line view
 * this repo used to ask people to paste. This card is that view, carried
 * inside the module and rendered on demand, so adding the panel to a
 * dashboard is one line - or two clicks, since it registers itself in the
 * card picker.
 *
 * Three things it deliberately does NOT do the way the pasted view did:
 *
 * 1. No card-mod. The view needed it to reach ha-card and turn on
 *    container-type (without which every cqw font silently resolves against
 *    the VIEWPORT instead of the card) and to strip the card chrome. Here
 *    the container lives on our own wrapper, and the chrome is switched off
 *    through ha-card's inherited custom properties - both of which cross the
 *    shadow boundary on their own. Nothing is pierced, and the last
 *    third-party dependency is gone.
 *
 * 2. Width, not transform. The old view shrank the plate with scale(0.75)
 *    because card-mod could not change how wide a panel view made the card,
 *    and a transform leaves the layout box at full size - so the card kept a
 *    band of dead space under the art, which is why the outline once
 *    appeared to float below the plate. Owning the box, `scale` is just a
 *    width, and the layout follows the art exactly.
 *
 * 3. It reports columns: full to a sections view. The plate is 1990x400,
 *    very nearly 5:1, and in a default-width section it would render as a
 *    letterbox slot too small to read.
 *
 * Options, both optional:
 *   scale    0-1, the fraction of the available width to use. Default 1.
 *   outline  CSS outline around the plate. Defaults to the 2px white one the
 *            panel has always had; set it to none to drop it.
 */

const PANEL_LAYOUT = {
    "type": "picture-elements",
    "image": "/tide16_static/plate-v3.png",
    "elements": [
      {
        "type": "custom:tide16-bars",
        "level_gain": 1.1,
        "idle_entity": "switch.tide16_audiophile_quotes",
        "style": {
          "left": "17.739%",
          "top": "21.500%",
          "width": "22.261%",
          "height": "29.250%",
          "transform": "translate(0, 0)",
          "pointer-events": "none"
        }
      },
      {
        "type": "custom:tide16-channels",
        "entity": "sensor.tide16_channel_names_held",
        "attribute": "channel_names",
        "font_size": "0.78cqw",
        "gap": "0.88cqw",
        "color": "#FFFFFF",
        "index_color": "#B7B8B8",
        "label_color": "#FFFFFF",
        "style": {
          "left": "0.854%",
          "top": "86.375%",
          "width": "63.3%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-toggle",
        "entity": "switch.tide16_auto_dim",
        "icon": "/tide16_static/sun.svg",
        "labels": {
          "on": "DIM",
          "off": "DIM"
        },
        "colors": {
          "on": "#FFFFFF",
          "off": "#8A8B8B"
        },
        "style": {
          "right": "83.1%",
          "left": "unset",
          "top": "41.6%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-buttons",
        "ratio": "7 / 2",
        "gap": "1.190cqw",
        "title": "Scenes:",
        "title_size": "1.070cqw",
        "title_gap": "1.190cqw",
        "buttons": [
          {
            "color": "#D93A2B",
            "hint": "Recall red scene",
            "tap": {
              "action": "button.press",
              "data": {
                "entity_id": "button.tide16_scene_red"
              }
            }
          },
          {
            "color": "#2FA84F",
            "hint": "Recall green scene",
            "tap": {
              "action": "button.press",
              "data": {
                "entity_id": "button.tide16_scene_green"
              }
            }
          },
          {
            "color": "#E8C22E",
            "hint": "Recall yellow scene",
            "tap": {
              "action": "button.press",
              "data": {
                "entity_id": "button.tide16_scene_yellow"
              }
            }
          },
          {
            "color": "#2F6FD0",
            "hint": "Recall blue scene",
            "tap": {
              "action": "button.press",
              "data": {
                "entity_id": "button.tide16_scene_blue"
              }
            }
          }
        ],
        "style": {
          "left": "42.513%",
          "top": "36.473%",
          "width": "3.216%",
          "height": "36.047%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "title": "Profiles",
        "title_image": "/tide16_static/dolby.png?v=1",
        "title_image_alt": "Dolby",
        "title_size": "1.070cqw",
        "title_color": "#BFC0C0",
        "title_gap": "0",
        "align": "center",
        "style": {
          "left": "46.181%",
          "top": "25.225%",
          "width": "10.201%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-inputs",
        "columns": 1,
        "rows": 4,
        "row_gap": "1.190cqw",
        "dot": "1.005cqw",
        "dot_gap": "0.402cqw",
        "size": "0.804cqw",
        "weight": "400",
        "color": "#B7B8B8",
        "active_entity": "select.tide16_dolby_profile",
        "active_attribute": null,
        "active_color": "#FFFFFF",
        "active_background": "#32CD32",
        "active_border": "1px solid #FFFFFF",
        "active_weight": "700",
        "items": [
          {
            "text": "Movie",
            "value": "movie",
            "hint": "Set Dolby profile: Movie",
            "tap": {
              "action": "select.select_option",
              "data": {
                "entity_id": "select.tide16_dolby_profile",
                "option": "movie"
              }
            }
          },
          {
            "text": "Music",
            "value": "music",
            "hint": "Set Dolby profile: Music",
            "tap": {
              "action": "select.select_option",
              "data": {
                "entity_id": "select.tide16_dolby_profile",
                "option": "music"
              }
            }
          },
          {
            "text": "Night",
            "value": "night",
            "hint": "Set Dolby profile: Night",
            "tap": {
              "action": "select.select_option",
              "data": {
                "entity_id": "select.tide16_dolby_profile",
                "option": "night"
              }
            }
          },
          {
            "text": "Off",
            "value": "off",
            "hint": "Turn the Dolby profile off",
            "tap": {
              "action": "select.select_option",
              "data": {
                "entity_id": "select.tide16_dolby_profile",
                "option": "off"
              }
            }
          }
        ],
        "style": {
          "left": "49.121%",
          "top": "36.473%",
          "width": "4.472%",
          "height": "36.047%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "size": "3.850cqw",
        "color": "#E7E8E8",
        "row_gap": "0",
        "align": "right",
        "rows": [
          {
            "entity": "sensor.tide16_volume_integer",
            "placeholder": "-.-"
          }
        ],
        "style": {
          "right": "86.231%",
          "left": "unset",
          "top": "21.660%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "size": "2.028cqw",
        "color": "#DFE0E0",
        "row_gap": "0",
        "rows": [
          {
            "entity": "sensor.tide16_volume_decimal",
            "prefix": ".",
            "placeholder": ""
          }
        ],
        "style": {
          "left": "14.070%",
          "top": "28.885%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "size": "1.141cqw",
        "color": "#E7E8E8",
        "row_gap": "0",
        "rows": [
          {
            "entity": "sensor.tide16_source"
          }
        ],
        "style": {
          "left": "6.734%",
          "top": "49.929%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "size": "0.844cqw",
        "row_gap": "0.010cqw",
        "rows": [
          {
            "label": "Rate:",
            "entity": "sensor.tide16_stream",
            "attribute": "sample_rate"
          },
          {
            "label": "Decoder:",
            "entity": "sensor.tide16_stream",
            "attribute": "decoder_type"
          },
          {
            "label": "Stream:",
            "entity": "sensor.tide16_stream"
          }
        ],
        "style": {
          "left": "6.784%",
          "top": "63.651%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "size": "0.724cqw",
        "color": "#A96BF5",
        "row_gap": "0",
        "rows": [
          {
            "entity": "sensor.tide16_status"
          }
        ],
        "style": {
          "left": "6.734%",
          "top": "58.950%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "conditional",
        "conditions": [
          {
            "entity": "switch.tide16_mute",
            "state": "on"
          }
        ],
        "elements": [
          {
            "type": "custom:tide16-readout",
            "title": "Mute",
            "title_color": "#D93A2B",
            "title_size": "0.894cqw",
            "title_gap": "0",
            "align": "right",
            "style": {
              "right": "60.302%",
              "left": "unset",
              "top": "32.847%",
              "transform": "translate(0, 0)"
            }
          }
        ]
      },
      {
        "type": "custom:tide16-inputs",
        "columns": 6,
        "rows": 2,
        "row_gap": "0.503cqw",
        "dot": "0.854cqw",
        "dot_gap": "0.302cqw",
        "size": "0.804cqw",
        "color": "#B7B8B8",
        "active_entity": "media_player.tide16",
        "active_attribute": "source",
        "active_color": "#FFFFFF",
        "active_background": "#32CD32",
        "active_border": "1px solid #FFFFFF",
        "active_size": "0.954cqw",
        "background": "#333333",
        "border": "1px solid #666666",
        "source_entity": "media_player.tide16",
        "source_attribute": "sources",
        "disabled_color": "#5E5F5F",
        "disabled_background": "#1F1F1F",
        "disabled_border": "1px solid #3A3A3A",
        "items": [
          {
            "text": "AppleTV",
            "id": "hdmi2",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "AppleTV"
              }
            }
          },
          {
            "text": "ARC / eARC",
            "id": "arc_earc",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "ARC / eARC"
              }
            }
          },
          {
            "text": "Bluetooth",
            "id": "bluetooth",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "Bluetooth"
              }
            }
          },
          {
            "text": "BR-DVD",
            "id": "hdmi3",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "BR-DVD"
              }
            }
          },
          {
            "text": "RCA",
            "id": "rca",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "RCA"
              }
            }
          },
          {
            "text": "Roku",
            "id": "hdmi1",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "Roku"
              }
            }
          },
          {
            "text": "SPDIF 1",
            "id": "spdif1",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "SPDIF 1"
              }
            }
          },
          {
            "text": "SPDIF 2",
            "id": "spdif2",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "SPDIF 2"
              }
            }
          },
          {
            "text": "TOSLINK 1",
            "id": "toslink1",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "TOSLINK 1"
              }
            }
          },
          {
            "text": "TOSLINK 2",
            "id": "toslink2",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "TOSLINK 2"
              }
            }
          },
          {
            "text": "USB",
            "id": "usb",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "USB"
              }
            }
          },
          {
            "text": "XLR",
            "id": "xlr",
            "tap": {
              "action": "media_player.select_source",
              "data": {
                "entity_id": "media_player.tide16",
                "source": "XLR"
              }
            }
          }
        ],
        "style": {
          "left": "17.487%",
          "top": "3.250%",
          "width": "50.804%",
          "height": "13.000%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-glyph",
        "image": "/tide16_static/bt.png",
        "hint": "Pair a Bluetooth device",
        "tap": {
          "action": "button.press",
          "data": {
            "entity_id": "button.tide16_bluetooth_pair"
          }
        },
        "style": {
          "left": "64.221%",
          "top": "3.750%",
          "width": "2.412%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "title": "PAIR",
        "title_size": "0.804cqw",
        "title_color": "#B7B8B8",
        "title_gap": "0",
        "align": "center",
        "style": {
          "left": "64.221%",
          "top": "16.750%",
          "width": "2.412%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-glyph",
        "image": "/tide16_static/power.png",
        "hint": "Power off the Tide16",
        "tap": {
          "action": "media_player.turn_off",
          "data": {
            "entity_id": "media_player.tide16"
          }
        },
        "color_entity": "media_player.tide16",
        "color_on": "#B300FF",
        "color_off": "#F52727",
        "style": {
          "left": "56.681%",
          "top": "43.938%",
          "width": "2.316%",
          "height": "12.375%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-glyph",
        "image": "/tide16_static/reboot.png",
        "hint": "Reboot the Tide16",
        "tap": {
          "action": "button.press",
          "data": {
            "entity_id": "button.tide16_reboot"
          }
        },
        "color": "#FF3B30",
        "busy_colors": [
          "#B300FF",
          "#F52727"
        ],
        "busy_interval": 1000,
        "busy_min_steps": 5,
        "busy_timeout": 60000,
        "busy_entity": "media_player.tide16",
        "busy_live_states": [
          "on"
        ],
        "button": true,
        "icon_scale": 0.688,
        "style": {
          "left": "64.221%",
          "top": "79.250%",
          "width": "2.412%",
          "height": "12.000%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "title": "Reboot",
        "title_size": "0.804cqw",
        "title_color": "#FF3B30",
        "title_gap": "0",
        "align": "center",
        "style": {
          "left": "64.221%",
          "top": "92.250%",
          "width": "2.412%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-knob-labels",
        "gap": "0.458cqw",
        "color": "#000",
        "size": "1.012cqw",
        "weight": "700",
        "labels": [
          {
            "at": 12,
            "text": [
              "Mute:",
              "On"
            ],
            "hint": "Mute on",
            "tap": {
              "action": "switch.turn_on",
              "data": {
                "entity_id": "switch.tide16_mute"
              }
            }
          },
          {
            "at": 6,
            "text": [
              "Mute:",
              "Off"
            ],
            "hint": "Mute off",
            "tap": {
              "action": "switch.turn_off",
              "data": {
                "entity_id": "switch.tide16_mute"
              }
            }
          },
          {
            "at": 3,
            "text": "Vol:+10",
            "hint": "Volume up 10 dB",
            "tap": {
              "action": "minidsp_tide16.volume_step",
              "data": {
                "delta": 10
              }
            }
          },
          {
            "at": 4.5,
            "text": "Vol:+20",
            "hint": "Volume up 20 dB",
            "tap": {
              "action": "minidsp_tide16.volume_step",
              "data": {
                "delta": 20
              }
            }
          },
          {
            "at": 2,
            "text": "Vol:+5",
            "hint": "Volume up 5 dB",
            "tap": {
              "action": "minidsp_tide16.volume_step",
              "data": {
                "delta": 5
              }
            }
          },
          {
            "at": 1,
            "text": "Vol:+2",
            "hint": "Volume up 2 dB",
            "tap": {
              "action": "minidsp_tide16.volume_step",
              "data": {
                "delta": 2
              }
            }
          },
          {
            "at": 11,
            "text": "Vol:-2",
            "hint": "Volume down 2 dB",
            "tap": {
              "action": "minidsp_tide16.volume_step",
              "data": {
                "delta": -2
              }
            }
          },
          {
            "at": 10,
            "text": "Vol:-5",
            "hint": "Volume down 5 dB",
            "tap": {
              "action": "minidsp_tide16.volume_step",
              "data": {
                "delta": -5
              }
            }
          },
          {
            "at": 9,
            "text": "Vol:-10",
            "hint": "Volume down 10 dB",
            "tap": {
              "action": "minidsp_tide16.volume_step",
              "data": {
                "delta": -10
              }
            }
          },
          {
            "at": 7.5,
            "text": "Vol:-20",
            "hint": "Volume down 20 dB",
            "tap": {
              "action": "minidsp_tide16.volume_step",
              "data": {
                "delta": -20
              }
            }
          }
        ],
        "style": {
          "left": "78.794%",
          "top": "22.375%",
          "width": "11.357%",
          "height": "56.500%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "size": "0.980cqw",
        "color": "#000",
        "row_gap": "0.150cqw",
        "rows": [
          {
            "label": "Tide FW:",
            "entity": "sensor.tide16_versions",
            "attribute": "tide",
            "alert_entity": "binary_sensor.tide16_firmware_update",
            "alert_color": "#A33F00",
            "alert_weight": 700
          },
          {
            "label": "HDMI FW:",
            "entity": "sensor.tide16_versions",
            "attribute": "hdmi"
          }
        ],
        "badge": {
          "image": "/tide16_static/swu.png",
          "alt": "Update available",
          "hint": "Use the Device Console to update FW",
          "entity": "binary_sensor.tide16_firmware_update",
          "size": "2.157cqw",
          "min_opacity": 0.05,
          "period": 2
        },
        "style": {
          "left": "69.397%",
          "top": "86.000%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "title": `v${TIDE16_VERSION}`,
        "title_size": "0.980cqw",
        "title_color": "#000",
        "title_gap": "0.150cqw",
        "size": "0.980cqw",
        "color": "#000",
        "rows": [
          {
            "clock": true,
            "offset_entity": "sensor.tide16_clock_offset",
            "offset_max": 43200,
            "alert_color": "#8B0000",
            "alert_weight": 700,
            "alert_hint": "The Tide16 NTP time updates are out of sync on the local network"
          }
        ],
        "align": "right",
        "style": {
          "right": "0.854%",
          "left": "unset",
          "top": "86.000%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "conditional",
        "conditions": [
          {
            "entity": "binary_sensor.tide16_atmos",
            "state": "on"
          }
        ],
        "elements": [
          {
            "type": "image",
            "image": "/tide16_static/badge-dolby-atmos.png",
            "style": {
              "left": "15.578%",
              "top": "61.250%",
              "width": "6.030%",
              "transform": "translate(0, 0)",
              "pointer-events": "none"
            }
          }
        ]
      },
      {
        "type": "conditional",
        "conditions": [
          {
            "entity": "binary_sensor.tide16_atmos",
            "state": "off"
          },
          {
            "entity": "select.tide16_upmixer",
            "state": "DTS-X"
          }
        ],
        "elements": [
          {
            "type": "image",
            "image": "/tide16_static/badge-dtsx.png",
            "style": {
              "left": "15.578%",
              "top": "61.250%",
              "width": "6.030%",
              "transform": "translate(0, 0)",
              "pointer-events": "none"
            }
          }
        ]
      },
      {
        "type": "conditional",
        "conditions": [
          {
            "entity": "binary_sensor.tide16_atmos",
            "state": "off"
          },
          {
            "entity": "select.tide16_upmixer",
            "state": "Dolby"
          }
        ],
        "elements": [
          {
            "type": "image",
            "image": "/tide16_static/badge-dolby-audio.png",
            "style": {
              "left": "15.578%",
              "top": "61.250%",
              "width": "6.030%",
              "transform": "translate(0, 0)",
              "pointer-events": "none"
            }
          }
        ]
      },
      {
        "type": "image",
        "image": "/tide16_static/dirac-white.png",
        "tap_action": {
          "action": "perform-action",
          "perform_action": "switch.toggle",
          "target": {
            "entity_id": "switch.tide16_dirac_live"
          }
        },
        "style": {
          "left": "22.211%",
          "top": "60.250%",
          "width": "2.814%",
          "transform": "translate(0, 0)",
          "cursor": "pointer"
        }
      },
      {
        "type": "custom:tide16-readout",
        "title": "Modes",
        "title_image": "/tide16_static/dolby.png?v=1",
        "title_image_alt": "Dolby",
        "title_size": "1.070cqw",
        "title_color": "#BFC0C0",
        "title_gap": "0",
        "align": "center",
        "style": {
          "left": "59.598%",
          "top": "25.225%",
          "width": "10.201%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-inputs",
        "columns": 1,
        "rows": 3,
        "row_gap": "1.190cqw",
        "dot": "1.005cqw",
        "dot_gap": "0.402cqw",
        "size": "0.804cqw",
        "weight": "400",
        "color": "#B7B8B8",
        "active_entity": "select.tide16_upmixer",
        "active_attribute": null,
        "active_color": "#FFFFFF",
        "active_background": "#32CD32",
        "active_border": "1px solid #FFFFFF",
        "active_weight": "700",
        "items": [
          {
            "text": "Native",
            "value": "Native",
            "hint": "Set upmixer: Native",
            "tap": {
              "action": "select.select_option",
              "data": {
                "entity_id": "select.tide16_upmixer",
                "option": "Native"
              }
            }
          },
          {
            "text": "Dolby",
            "value": "Dolby",
            "hint": "Set upmixer: Dolby",
            "tap": {
              "action": "select.select_option",
              "data": {
                "entity_id": "select.tide16_upmixer",
                "option": "Dolby"
              }
            }
          },
          {
            "text": "DTS-X",
            "value": "DTS-X",
            "hint": "Set upmixer: DTS-X",
            "tap": {
              "action": "select.select_option",
              "data": {
                "entity_id": "select.tide16_upmixer",
                "option": "DTS-X"
              }
            }
          }
        ],
        "style": {
          "left": "62.513%",
          "top": "36.473%",
          "width": "4.472%",
          "height": "25.575%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "title": "In",
        "title_size": "0.744cqw",
        "title_color": "#FFFFFF",
        "title_gap": "0",
        "style": {
          "left": "26.281%",
          "top": "58.726%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "title": "Out",
        "title_size": "0.744cqw",
        "title_color": "#FFFFFF",
        "title_gap": "0",
        "style": {
          "left": "31.357%",
          "top": "58.726%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "title": "Preset",
        "title_size": "0.744cqw",
        "title_color": "#FFFFFF",
        "title_gap": "0",
        "style": {
          "left": "36.332%",
          "top": "58.726%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "size": "1.075cqw",
        "color": "#FFFFFF",
        "row_gap": "0",
        "rows": [
          {
            "entity": "sensor.tide16_input_format"
          }
        ],
        "style": {
          "left": "26.281%",
          "top": "64.723%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-readout",
        "size": "0.844cqw",
        "color": "#FFFFFF",
        "row_gap": "0",
        "rows": [
          {
            "entity": "sensor.tide16_sample_rate_khz"
          }
        ],
        "style": {
          "left": "26.281%",
          "top": "71.431%",
          "transform": "translate(0, 0)",
          "width": "4.774%"
        }
      },
      {
        "type": "custom:tide16-readout",
        "size": "1.075cqw",
        "color": "#FFFFFF",
        "row_gap": "0",
        "rows": [
          {
            "entity": "sensor.tide16_speaker_config"
          }
        ],
        "style": {
          "left": "31.357%",
          "top": "64.723%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "conditional",
        "conditions": [
          {
            "entity": "binary_sensor.tide16_upmixed",
            "state": "on"
          }
        ],
        "elements": [
          {
            "type": "custom:tide16-readout",
            "title": "Upmixed",
            "title_size": "0.844cqw",
            "title_color": "#FFFFFF",
            "title_gap": "0",
            "style": {
              "left": "31.357%",
              "top": "71.431%",
              "transform": "translate(0, 0)"
            }
          }
        ]
      },
      {
        "type": "custom:tide16-readout",
        "size": "1.075cqw",
        "color": "#FFFFFF",
        "row_gap": "0",
        "rows": [
          {
            "entity": "sensor.tide16_preset",
            "attribute": "preset_index"
          }
        ],
        "style": {
          "left": "36.332%",
          "top": "64.723%",
          "transform": "translate(0, 0)"
        }
      },
      {
        "type": "custom:tide16-select",
        "entity": "select.tide16_filter_preset",
        "title": "Filter Preset",
        "hint": "Choose a filter preset",
        "style": {
          "left": "53.266%",
          "top": "73.500%",
          "width": "8.945%",
          "height": "11.750%",
          "transform": "translate(0, 0)"
        }
      }
    ]
  };

/** Point the layout at THIS integration's entities when they were suffixed.
 *
 * The layouts name entities by their default ids (media_player.tide16,
 * sensor.tide16_source...). When another integration already holds those ids
 * - an older install, or a second Tide16 integration kept side by side -
 * Home Assistant hands this one `_2` ids, and the card would quietly read and
 * drive the OTHER integration's entities. The frontend's entity registry says
 * which platform owns each id, so every exact id in the layout whose default
 * name belongs to someone else is swapped for the `tide16` entity carrying the
 * same name plus a numeric suffix. With no collision the map is empty and the
 * layout is untouched. `remap_entities: false` on the card turns it off.
 */
// The integration's domain: minidsp_tide16 since the merge, tide16 upstream.
const TIDE16_PLATFORMS = ['minidsp_tide16', 'tide16'];

function tide16EntityMap(hass) {
  const reg = hass && hass.entities;
  if (!reg) return null;
  const map = {};
  Object.keys(reg).forEach((eid) => {
    const e = reg[eid];
    if (!e || !TIDE16_PLATFORMS.includes(e.platform)) return;
    const base = eid.replace(/_\d+$/, '');
    if (base === eid) return;
    const holder = reg[base];
    if (holder && !TIDE16_PLATFORMS.includes(holder.platform)) map[base] = eid;
  });
  return map;
}

function tide16Remap(node, map) {
  if (!map || !Object.keys(map).length) return node;
  if (typeof node === 'string') return Object.prototype.hasOwnProperty.call(map, node) ? map[node] : node;
  if (Array.isArray(node)) return node.map((n) => tide16Remap(n, map));
  if (node && typeof node === 'object') {
    const out = {};
    Object.keys(node).forEach((k) => { out[k] = tide16Remap(node[k], map); });
    return out;
  }
  return node;
}

/** Rebuild a card when the entity map changes; called on every hass tick. */
function tide16TrackMap(card, hass) {
  if (card._config && card._config.remap_entities === false) return;
  const map = tide16EntityMap(hass);
  if (map === null) return; // registry not loaded yet
  const stamp = JSON.stringify(map);
  if (stamp === card._entityStamp) return;
  card._entityStamp = stamp;
  card._entityMap = map;
  // Built before hass arrived with nothing to swap, and still nothing: keep it.
  if (!Object.keys(map).length && !card._renderedWithMap) return;
  card._rebuild();
}

class Tide16Panel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._token = 0;
  }

  setConfig(config) {
    this._config = config || {};
    this._card = null;
    this.shadowRoot.innerHTML = '';
    this._render();
  }

  _rebuild() {
    this._card = null;
    this.shadowRoot.innerHTML = '';
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    tide16TrackMap(this, hass);
    if (this._card) this._card.hass = hass;
    this._wakeToChannels();
  }

  get hass() {
    return this._hass;
  }

  /** Put the meter back on the DSP channels when the unit comes back.
   *
   * Off means off: the unit cannot be polled at all, and the window shows the
   * idle panel whichever meter was last chosen. Coming back is a fresh start,
   * and the thing the panel is for is the unit's own sixteen channels - so a
   * spectrum left up from last night should not be what greets it. A future
   * sleep state behaves the same way, because it is the same question:
   * can we talk to it or not.
   *
   * Only on the transition, so the choice is still the user's for as long as
   * the unit stays up. Every open dashboard runs this, and they all set the
   * same value on the same edge - the check below means the first one to
   * arrive is the only one that writes.
   */
  _wakeToChannels() {
    const spec = this._config.spectrum;
    if (!spec || !spec.mode_entity || spec.wake_to_channels === false) return;
    const hass = this._hass;
    if (!hass) return;

    const watch = spec.wake_entity || 'media_player.tide16';
    const away = spec.wake_states || WAKE_AWAY_STATES;
    const st = hass.states[watch];
    const gone = !st || away.indexOf(String(st.state)) !== -1;

    const was = this._unitGone;
    this._unitGone = gone;
    if (was !== true || gone) return; // only the away -> here edge

    const channels = spec.channels_state || 'Channels';
    const mode = hass.states[spec.mode_entity];
    if (!mode || String(mode.state) === channels) return;
    hass.callService('input_select', 'select_option', {
      entity_id: spec.mode_entity,
      option: channels,
    });
  }

  async _render() {
    // _render is async, and setConfig can land again before it finishes.
    // The token is what stops a superseded run from appending its card into
    // a wrapper that is no longer in the tree.
    const token = ++this._token;
    const asked = Number(this._config.scale);
    const scale = Number.isFinite(asked) && asked > 0 ? Math.min(asked, 1) : 1;
    const outline =
      this._config.outline === undefined ? '2px solid #FFFFFF' : this._config.outline;

    const style = document.createElement('style');
    style.textContent = `
      :host {
        display: block;
        /* Air above the plate. Padding on the host rather than a margin on
           the wrapper: a margin would collapse out of the shadow root and
           land on whatever the card sits under, which is how the panel ended
           up flush against the top of the view. */
        padding-top: 20px;
      }
      .wrap {
        /* The whole reason this element exists rather than a bare
           picture-elements card: every font on the panel is sized in cqw,
           and cqw only means "percent of the card" if something declares
           itself a container. Container queries resolve through shadow
           boundaries, so declaring it here reaches the elements inside the
           picture-elements card without touching that card at all. */
        container-type: inline-size;
        margin: 0 auto;
        /* Clips the square-cornered plate to the rounded box, so the outline
           traces a rounded card around a rounded image instead of cutting
           across four square corners. */
        overflow: hidden;
        border-radius: var(--ha-card-border-radius, 12px);
        /* Inherited custom properties, so they reach the ha-card inside the
           picture-elements shadow root without piercing it. Without them the
           plate sits on a second, visible card - theme background, border
           and shadow around the artwork. */
        --ha-card-background: transparent;
        --ha-card-box-shadow: none;
        --ha-card-border-width: 0;
        --ha-card-border-radius: 0;
      }
    `;

    const wrap = document.createElement('div');
    wrap.className = 'wrap';
    wrap.style.width = `${(scale * 100).toFixed(4)}%`;
    wrap.style.outline = outline;
    this.shadowRoot.append(style, wrap);

    let card;
    try {
      const helpers = await window.loadCardHelpers();
      if (token !== this._token) return;
      // Deep clone. A Lovelace card deep-freezes the config it is handed,
      // and PANEL_LAYOUT is module state - freezing it would break every
      // later instance of this card on the page.
      this._renderedWithMap = !!(this._entityMap && Object.keys(this._entityMap).length);
      card = helpers.createCardElement(tide16Remap(withSpectrum(
        JSON.parse(JSON.stringify(PANEL_LAYOUT)), this._config.spectrum), this._entityMap));
    } catch (err) {
      if (token !== this._token) return;
      wrap.textContent = `Tide16 panel failed to build: ${err}`;
      return;
    }

    if (this._hass) card.hass = this._hass;
    wrap.appendChild(card);
    this._card = card;
  }

  getCardSize() {
    return 4;
  }

  getGridOptions() {
    // 1990x400 of artwork. A sections view hands a card four columns by
    // default, which would letterbox the plate to about 340px wide.
    return { columns: 'full', min_columns: 6, rows: 'auto' };
  }

  static getStubConfig() {
    return {};
  }
}

if (!customElements.get('tide16-panel')) {
  customElements.define('tide16-panel', Tide16Panel);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === 'tide16-panel')) {
  window.customCards.push({
    type: 'tide16-panel',
    name: 'miniDSP Tide16 Panel',
    description:
      'The Tide16 front panel - live 16-channel meter, source selector, scenes, volume and every readout.',
    preview: true,
    documentationURL: 'https://github.com/speedtoys/Minidsp-Tide16-ControlCard',
  });
}

/**
 * tide16-mini - the mini tile as a card, with its parts switched by option.
 *
 * The tile started as a block of picture-elements config in the README, and
 * a block of config can only lose a part by somebody deleting elements and
 * moving the rest by hand.  Here the layout is built from two options, so a
 * part that is off is simply not drawn and the rest close up around it:
 *
 *   labels: none | numbers | names | both   (under the bars)
 *   side: [volume, source, decoder]         (the box on the left)
 *
 * Nothing set is the bare meter across the whole tile.  The side box always
 * stacks volume, source, decoder in that order, whichever are listed, and is
 * centred in the tile's height when it does not fill it.  With all three the
 * tile is the README's, to the percent.
 *
 * Every size is px.  A picture-elements card is not a container, so cqw
 * would resolve against the viewport and the text would come out several
 * times too big.
 */
const MINI_LABELS = ['none', 'numbers', 'names', 'both'];
const MINI_SIDE = ['volume', 'source', 'decoder'];

// How far the label row hangs below the meter box, which the box's height
// gives back so the row lands inside the tile.  Font plus gap per line.
const MINI_LABEL_PX = { none: 0, numbers: 15, names: 33, both: 48 };

// Each side section's share of the tile's height, and its contents' offsets
// from the top of that share.  Measured off the hand-built tile: volume
// 0-45%, its rule at 45%, source 45-79%, decoder 79-100%.
const MINI_SECTION_H = { volume: 45, source: 34, decoder: 21 };
const MINI_RULE = '#444444';

const miniPct = (n) => `${Math.round(n * 1000) / 1000}%`;
const miniAt = (style) => ({ ...style, transform: 'translate(0, 0)' });

// A titled-but-empty readout is just a positioned box - drawn as a rule.
const miniRule = (style) => ({
  type: 'custom:tide16-readout',
  title: ' ',
  title_size: '0',
  title_gap: '0',
  style: miniAt({ ...style, background: MINI_RULE }),
});

const miniBadge = (image, conditions, top) => ({
  type: 'conditional',
  conditions,
  elements: [{
    type: 'image',
    image: `/tide16_static/${image}`,
    style: miniAt({ left: '3.5%', top: miniPct(top), width: '11.5%', 'pointer-events': 'none' }),
  }],
});

const MINI_SECTIONS = {
  volume: (top) => [
    {
      type: 'custom:tide16-readout',
      size: '46px',
      color: '#E7E8E8',
      row_gap: '0',
      align: 'right',
      rows: [{ entity: 'sensor.tide16_volume_integer', placeholder: '-.-' }],
      style: miniAt({ right: '79.5%', left: 'unset', top: miniPct(top + 3) }),
    },
    {
      type: 'custom:tide16-readout',
      title: 'dB',
      title_size: '16px',
      title_color: '#808080',
      title_gap: '0',
      style: miniAt({ left: '20.8%', top: miniPct(top + 5.5) }),
    },
    {
      type: 'custom:tide16-readout',
      size: '24px',
      color: '#DFE0E0',
      row_gap: '0',
      rows: [{ entity: 'sensor.tide16_volume_decimal', prefix: '.', placeholder: '' }],
      style: miniAt({ left: '20.6%', top: miniPct(top + 21) }),
    },
  ],
  source: (top) => [
    {
      type: 'custom:tide16-readout',
      title: 'Source',
      title_size: '12px',
      title_gap: '3px',
      size: '18px',
      color: '#E7E8E8',
      rows: [{ entity: 'sensor.tide16_source' }],
      scroll: true,
      style: miniAt({ left: '3.5%', top: miniPct(top + 2), width: '24%' }),
    },
  ],
  decoder: (top) => {
    const dirac = { entity: 'switch.tide16_dirac_live', state: 'on' };
    const plain = { entity: 'binary_sensor.tide16_atmos', state: 'off' };
    return [
      miniBadge('badge-dolby-atmos.png',
        [{ entity: 'binary_sensor.tide16_atmos', state: 'on' }], top + 2),
      miniBadge('badge-dtsx.png',
        [plain, { entity: 'select.tide16_upmixer', state: 'DTS-X' }], top + 2),
      miniBadge('badge-dolby-audio.png',
        [plain, { entity: 'select.tide16_upmixer', state: 'Dolby' }], top + 2),
      {
        type: 'conditional',
        conditions: [dirac],
        elements: [{
          type: 'image',
          image: '/tide16_static/dirac-white.png',
          style: miniAt({ left: '16.2%', top: miniPct(top + 2.5), width: '4.4%', 'pointer-events': 'none' }),
        }],
      },
      {
        type: 'conditional',
        conditions: [dirac,
          { entity: 'sensor.tide16_dirac_filter_type', state: 'Dirac Active Room Treatment' }],
        elements: [{
          type: 'custom:tide16-readout',
          title: 'ART',
          title_size: '13px',
          title_color: '#FFFFFF',
          title_gap: '0',
          style: miniAt({ left: '21.4%', top: miniPct(top + 6) }),
        }],
      },
    ];
  },
};

/** Read the two options, refusing anything that is not one of them - a typo
 * that quietly drew nothing would look like a bug in the card. */
function miniOptions(config) {
  const labels = config.labels === undefined ? 'none' : String(config.labels);
  if (MINI_LABELS.indexOf(labels) === -1) {
    throw new Error(`tide16-mini: labels must be one of ${MINI_LABELS.join(', ')}`);
  }
  let side = config.side === undefined || config.side === null ? [] : config.side;
  if (!Array.isArray(side)) side = [side];
  side = side.map(String);
  const bad = side.filter((s) => MINI_SIDE.indexOf(s) === -1);
  if (bad.length) {
    throw new Error(`tide16-mini: unknown side ${bad.join(', ')} - use ${MINI_SIDE.join(', ')}`);
  }
  // Fixed order, whatever order they were listed in.
  return { labels, side: MINI_SIDE.filter((s) => side.indexOf(s) !== -1) };
}

function miniLayout(config) {
  const { labels, side } = miniOptions(config);
  const elements = [];

  const bars = {
    type: 'custom:tide16-bars',
    level_gain: 1.1,
    idle_entity: 'switch.tide16_audiophile_quotes',
    numbers: labels === 'numbers' || labels === 'both',
    numbers_size: '11px',
    numbers_gap: '3px',
    names: labels === 'names' || labels === 'both',
    names_size: '11px',
    names_gap: '3px',
    names_height: '30px',
    // Anything else tide16-bars takes, for whoever wants to tune the meter.
    ...(config.bars || {}),
  };
  const left = side.length ? 31 : 1.5;
  bars.style = miniAt({
    left: miniPct(left),
    top: '3%',
    width: miniPct(side.length ? 68 : 97),
    height: `calc(94% - ${MINI_LABEL_PX[labels]}px)`,
  });
  elements.push(bars);

  if (side.length) {
    const total = side.reduce((sum, s) => sum + MINI_SECTION_H[s], 0);
    let top = (100 - total) / 2;
    side.forEach((s, i) => {
      elements.push(...MINI_SECTIONS[s](top));
      top += MINI_SECTION_H[s];
      // The one rule the tile has always had: under the volume, when
      // something follows it.
      if (s === 'volume' && i < side.length - 1) {
        elements.push(miniRule({ left: '2%', top: miniPct(top), width: '26%', height: '1px' }));
      }
    });
    elements.push(miniRule({ left: '29%', top: '4%', width: '1px', height: '92%' }));
  }

  return {
    type: 'picture-elements',
    // A plain dark 1000x280 canvas; its proportions set the tile's height.
    image: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1000 280'><rect width='1000' height='280' fill='%230b1013'/></svg>",
    elements,
  };
}

class Tide16Mini extends HTMLElement {
  constructor() {
    super();
    this._token = 0;
  }

  setConfig(config) {
    this._config = config || {};
    // Thrown here, not at render, so the editor shows the error in place.
    this._layout = miniLayout(this._config);
    this._side = miniOptions(this._config).side;
    this._card = null;
    this.innerHTML = '';
    this._render();
  }

  _rebuild() {
    this._card = null;
    this.innerHTML = '';
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    tide16TrackMap(this, hass);
    if (this._card) this._card.hass = hass;
  }

  get hass() {
    return this._hass;
  }

  async _render() {
    // Same guard as the panel: a later setConfig supersedes this run.
    const token = ++this._token;
    let card;
    try {
      const helpers = await window.loadCardHelpers();
      if (token !== this._token) return;
      this._renderedWithMap = !!(this._entityMap && Object.keys(this._entityMap).length);
      card = helpers.createCardElement(tide16Remap(this._layout, this._entityMap));
    } catch (err) {
      if (token !== this._token) return;
      this.textContent = `Tide16 mini tile failed to build: ${err}`;
      return;
    }
    if (this._hass) card.hass = this._hass;
    this.appendChild(card);
    this._card = card;
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    // With the side box the left block crowds the meter below full width.
    return this._side && this._side.length
      ? { columns: 'full', rows: 'auto' }
      : { columns: 6, min_columns: 3, rows: 'auto' };
  }

  static getStubConfig() {
    return {};
  }
}

if (!customElements.get('tide16-mini')) {
  customElements.define('tide16-mini', Tide16Mini);
}

if (!window.customCards.some((c) => c.type === 'tide16-mini')) {
  window.customCards.push({
    type: 'tide16-mini',
    name: 'miniDSP Tide16 Mini Tile',
    description:
      'The 16-channel meter for a dashboard column, with optional channel numbers or names and a side box for volume, source and decoder.',
    preview: true,
    documentationURL: 'https://github.com/speedtoys/Minidsp-Tide16-ControlCard',
  });
}

/**
 * Register with whichever registry the frontend actually ends up using.
 *
 * The integration serves this module through frontend.add_extra_js_url, and
 * Home Assistant imports it at about 60ms - well before its own bundle
 * installs the scoped custom element registry that REPLACES
 * window.customElements. Everything defined above therefore lands in the
 * NATIVE registry.
 *
 * The browser still upgrades those tags wherever they appear, which is why
 * the seven picture-elements elements have always worked. But the frontend
 * looks a CARD up in the replacement registry, so a card registered only
 * natively answers "Custom element doesn't exist" and the view renders a
 * Configuration error instead. Nothing above this line is enough on its own.
 *
 * So: register now, and register again if the registry is swapped out from
 * under us. A fresh subclass each time - a constructor may only be used once
 * per registry, and this is the same class going into a second one.
 */

const TIDE16_ELEMENTS = [
  ['tide16-bars', Tide16Bars],
  ['tide16-channels', Tide16Channels],
  ['tide16-buttons', Tide16Buttons],
  ['tide16-glyph', Tide16Glyph],
  ['tide16-knob-labels', Tide16KnobLabels],
  ['tide16-readout', Tide16Readout],
  ['tide16-inputs', Tide16Inputs],
  ['tide16-select', Tide16Select],
  ['tide16-toggle', Tide16Toggle],
  ['tide16-panel', Tide16Panel],
  ['tide16-mini', Tide16Mini],
];

const tide16Register = (registry) => {
  TIDE16_ELEMENTS.forEach(([name, cls]) => {
    if (registry.get(name)) return;
    try {
      registry.define(name, class extends cls {});
    } catch (err) {
      console.warn(`TIDE16: could not register <${name}>`, err);
    }
  });
};

const tide16FirstRegistry = window.customElements;
tide16Register(tide16FirstRegistry);

// ha-card is the frontend's own, so its absence means this is not the
// frontend's registry yet and a swap is still to come. Bounded: a page that
// never swaps is a page where the first registration was already the right
// one, and a timer must not outlive that answer.
if (!tide16FirstRegistry.get('ha-card')) {
  let waited = 0;
  const poll = setInterval(() => {
    waited += 200;
    if (window.customElements !== tide16FirstRegistry) {
      tide16Register(window.customElements);
      clearInterval(poll);
    } else if (waited >= 30000) {
      clearInterval(poll);
    }
  }, 200);
}

// Bumped with the repo tag. Printed on load so a stale cached copy is
// one glance in the console rather than a guess - the frontend caches
// /local/ hard, and the resource URL's ?v= is the only thing that busts
// it.
/** Add a second meter to the layout, drawn in the same window as the
 * channel bars and fed from a state attribute.
 *
 * The panel meters the unit's 16 DSP channels. This lets the same window
 * show something else measured about the same system - a spectrum, from a
 * microphone or a line input - as dots rather than bars, because 31 bands
 * will not fit as 31 bars.
 *
 * Nothing about the measurement is in here or anywhere else in this repo:
 * the card is handed an entity whose attribute is an array of dB values and
 * draws it. Where that array came from is somebody's own business, and an
 * install without one is untouched - the option defaults to absent.
 *
 * With `mode_entity` both meters are built and each shows itself when that
 * entity reads its own state, so switching between them costs a display
 * property rather than a rebuild of the card. Without it the spectrum simply
 * replaces the channels.
 */
// What counts as the unit being unreachable. Off is off - it cannot be polled
// at all - and a sleep state that an API call could wake would be the same
// question with a different name, so it belongs on this list too.
const WAKE_AWAY_STATES = ['off', 'unavailable', 'unknown', 'standby'];

function withSpectrum(layout, spec) {
  if (!spec || !spec.entity) return layout;
  const els = layout.elements || [];
  const i = els.findIndex((e) => e.type === 'custom:tide16-bars');
  if (i === -1) return layout;

  const channels = els[i];
  const {
    mode_entity: modeEntity,
    channels_state: channelsState = 'Channels',
    spectrum_state: spectrumState = 'Spectrum',
    toggle,
    ...rest
  } = spec;

  const meter = {
    type: 'custom:tide16-bars',
    // Same box on the plate, to the pixel.
    style: JSON.parse(JSON.stringify(channels.style || {})),
    source: 'entity',
    attribute: 'bands',
    marker: 'dot',
    // Gentler than the channel meter's, but only just. That one is a peak
    // meter and has to catch a transient; a spectrum is already an average
    // over its own window, so the only thing left to smooth is the step from
    // one dot row to the next.
    //
    // Not gentler than that, though: the analysis window is already ~0.5s of
    // delay before a reading is published, and a slow fall here adds to it
    // rather than hiding it. At 22 dB/s a band that stops falls for nearly
    // two seconds after the sound has gone, which reads as the display
    // lagging the room - because it is. Overridable, like everything here.
    attack_ms: 45,
    decay_db_s: 55,
    // The unit being in standby is the one thing this meter cannot see for
    // itself - its numbers come from elsewhere entirely - so it is told which
    // entity to watch. With the unit away it empties and the idle panel takes
    // the window, exactly as the channel meter does.
    gone_entity: 'media_player.tide16',
    // The idle panel belongs to the WINDOW, not to whichever meter happens
    // to be drawing it, so the quotes switch reaches this one too. Before
    // the spread, so a spectrum that states its own still wins.
    idle_entity: channels.idle_entity,
    ...rest,
  };

  if (!modeEntity) {
    els[i] = meter;
    return layout;
  }
  channels.show_when = { entity: modeEntity, state: channelsState };
  meter.show_when = { entity: modeEntity, state: spectrumState };
  els.splice(i + 1, 0, meter);

  // The switch itself, in the empty right half of the Source cell - the one
  // box on the plate with room for a control that is about what the screen
  // is showing rather than about the audio. Position and labels are both
  // overridable; these are just what fits the stock plate.
  els.push({
    type: 'custom:tide16-toggle',
    entity: modeEntity,
    labels: { [channelsState]: 'DSP', [spectrumState]: 'Freq' },
    ...(toggle || {}),
    style: {
      // Bottom row of the Source cell, against its right border. Held by the
      // right edge rather than the left so the source name, which shares the
      // row and grows from the left, can never run into it - "ARC / eARC" is
      // the longest the unit offers.
      right: '83.1%',
      left: 'unset',
      top: '49.6%',
      transform: 'translate(0, 0)',
      ...((toggle && toggle.style) || {}),
    },
  });
  return layout;
}

console.info(
  `%c TIDE16 ${TIDE16_VERSION} %c panel card + meter + legend + readouts + inputs + scenes + knob labels + glyphs `,
  'color:#0b1013;background:#ABACAC;font-weight:700',
  'color:#ABACAC;background:#0b1013'
);

.pragma library
// Controls and short guides shown from a game's Details. Buttons are the Nova's own labels:
// its pad is Xbox-style (A bottom, B right, X left, Y top) and emulators map consoles by position.
// Game controls come from the original manuals' button lists; every row says where it came from.

function norm(title) {
    return String(title || "").toLowerCase().replace(/\s*\((usa|u|europe|e|japan|j)\)/g, "").replace(/\s*\[[^\]]*\]/g, "").trim();
}

var EMULATORS = [
    { match: /^RetroArch/, name: "RetroArch", rows: [
        { label: "RetroArch menu", value: "Select + Y" },
        { label: "Save checkpoint", value: "Select + R1" },
        { label: "Load checkpoint", value: "Select + L1",
          detail: "RetroArch selects your newest numbered checkpoint when a game starts, so Select + L1 straight after launch picks up where your last checkpoint left off." },
        { label: "Older / newer slot", value: "Select + L3 / R3" },
        { label: "Quit to Library", value: "Select + Start" }
    ], source: "Nova controls set up and checked on 9 October 2026; slot behaviour from RetroArch's settings." },
    { match: /^NetherSX2/, name: "NetherSX2", rows: [
        { label: "Pause menu", value: "Back",
          detail: "Save or load a state, change settings or exit. PS2 buttons map by position: Cross A, Circle B, Square X, Triangle Y." }
    ], source: "Nova controls notes." },
    { match: /^Dolphin/, name: "Dolphin", rows: [
        { label: "Emulator menu", value: "Back", detail: "Save states and exit live here. Standard Android behaviour, not yet checked on this Nova." },
        { label: "Z", value: "R1" }, { label: "L / R", value: "Triggers" }, { label: "C-stick", value: "Right stick" }
    ], source: "Nova controls notes." },
    { match: /^melonDS/, name: "melonDS", rows: [
        { label: "Emulator menu", value: "Back", detail: "Save states, layout and exit. The icons along the top of the screen are melonDS's own shortcuts. Not yet checked on this Nova." }
    ], source: "melonDS on-screen controls, seen on this Nova on 16 October 2026." },
    { match: /^PPSSPP/, name: "PPSSPP", rows: [
        { label: "Emulator menu", value: "Back", detail: "Save states and exit live here. Standard Android behaviour, not yet checked on this Nova." }
    ], source: "Nova controls notes." }
];

var GAMES = [
    { system: "psx", titles: ["metal gear solid"], rows: [
        { label: "Move", value: "D-pad / left stick" },
        { label: "Punch, kick, action", value: "B  (Circle)", detail: "With your back to a wall, tap B to knock and draw a guard." },
        { label: "Crouch, then crawl", value: "A  (Cross)" },
        { label: "First-person view", value: "Y  (Triangle)" },
        { label: "Weapon, throw, choke", value: "X  (Square)" },
        { label: "Quick-change item / weapon", value: "L1 / R1" },
        { label: "Equip item / weapon", value: "L2 / R2" },
        { label: "Codec", value: "Select (tap)" },
        { label: "Pause", value: "Start" }
    ], tips: [
        { label: "Save the game", value: "Codec 140.96", detail: "Call Mei Ling on 140.96 to save to the memory card. That save lives in the game, separate from RetroArch checkpoints." },
        { label: "Meryl's frequency", value: "140.15", detail: "The game tells you it's on the back of the CD case: 140.15." },
        { label: "Disc 2", value: "Select + Y", detail: "When the game asks for disc 2: RetroArch menu → Quick Menu → Disc Control → Eject Disc, set Current Disc Index to 2, then Insert Disc. Both discs are in the playlist." },
        { label: "Torture", value: "Tap B fast", detail: "Mash Circle (B) to hold on. Not giving up changes which ending you get." },
        { label: "Boss order", value: "", detail: "Revolver Ocelot · M1 Tank · Ninja · Psycho Mantis · Sniper Wolf · Hind D · Sniper Wolf again · Vulcan Raven · Metal Gear REX · Liquid." }
    ], source: "Controls: Metal Gear Solid manual button list (PSX Data Center)." },
    { system: "ps2", titles: ["ssx 3"], rows: [
        { label: "Steer · speed · check", value: "Left stick / D-pad" },
        { label: "Crouch, release to jump", value: "A  (Cross)", detail: "Holding A stops you steering, so only hold it when the jump is straight ahead." },
        { label: "Boost (ground)", value: "X  (Square)", detail: "Square also gets you up faster after a wipeout." },
        { label: "Tweak (air)", value: "X  (Square)" },
        { label: "Grab (air)", value: "L1 · R1 · L2 · R2" },
        { label: "Handplant", value: "B  (Circle)" },
        { label: "Spins and flips", value: "D-pad", detail: "Pre-wind while crouched, or add late spins in the air." },
        { label: "Board presses", value: "Right stick" },
        { label: "Push / block a push", value: "Shoulders / L1 + R1" },
        { label: "Reset boarder", value: "Select" },
        { label: "Pause", value: "Start" }
    ], tips: [], source: "Controls: SSX 3 manual button list (PSX Data Center)." },
    { system: "snes", titles: ["super mario all-stars"], rows: [
        { label: "Jump", value: "A or B" },
        { label: "Run, fireball", value: "X or Y", detail: "In Super Mario Bros. 2 this button also picks up and throws." },
        { label: "Pause", value: "Start" },
        { label: "Choose a menu option", value: "Select" }
    ], tips: [
        { label: "Save in the game", value: "Start", detail: "Pause, then pick Save & Continue or Save & Quit. Seen on this Nova in Super Mario Bros. 3." },
        { label: "Your latest checkpoint", value: "Select + L1", detail: "Press it right after launch to jump to your newest numbered checkpoint." },
        { label: "Lost Levels World 9", value: "", detail: "Finish worlds 1–8 without using a single warp zone." }
    ], source: "Controls: Super Mario Wiki's All-Stars control tables." }
];

function emulatorFor(e) {
    var route = e && e.route ? e.route : "";
    for (var i = 0; i < EMULATORS.length; i++)
        if (EMULATORS[i].match.test(route)) return EMULATORS[i];
    return null;
}

function gameFor(e) {
    if (!e) return null;
    var t = norm(e.discSetName || e.title);
    for (var i = 0; i < GAMES.length; i++)
        if (GAMES[i].system === e.systemId && GAMES[i].titles.indexOf(t) !== -1) return GAMES[i];
    return null;
}

function available(e) {
    return !!(e && e.systemId !== "androidapps" && (gameFor(e) || emulatorFor(e)));
}

// Rows for the list panel: section headings are dim; a row's detail shows below the list.
function rows(e) {
    var out = [], g = gameFor(e), emu = emulatorFor(e);
    if (g) {
        out.push({ label: "In the game", value: "", dim: true, detail: g.source });
        g.rows.forEach(function(r) { out.push(r); });
        if (g.tips.length) {
            out.push({ label: "Stuck?", value: "", dim: true, detail: "Short notes for this game. Highlight one to read it." });
            g.tips.forEach(function(r) { out.push(r); });
        }
    }
    if (emu) {
        out.push({ label: emu.name, value: "", dim: true, detail: emu.source });
        emu.rows.forEach(function(r) { out.push(r); });
    }
    return out;
}

.pragma library
// Controls and short guides shown from a game's Details. Buttons are the Nova's own labels:
// its pad is Xbox-style (A bottom, B right, X left, Y top) and emulators map consoles by position.
// Game controls come from the original manuals' button lists; every row says where it came from.

function norm(title) {
    return String(title || "").toLowerCase().replace(/\s*\((usa|u|europe|e|japan|j)\)/g, "").replace(/\s*\[[^\]]*\]/g, "").trim();
}

var EMULATORS = [
    { match: /^Ship of Harkinian 9\.3\.1-android\.4$/, name: "Ship of Harkinian · native", rows: [
        { label: "Settings", value: "Android Back", detail: "This opens the port's settings. It is separate from the game's Start pause screen." },
        { label: "Save in the game", value: "Start → B → Save", detail: "Use the pause screen's Save prompt. The separate NOVA file was saved and reopened using touch controls. The owner also confirmed movement, action, pause, settings and sound; a physical save-button sequence is a separate check." },
        { label: "Touch buttons", value: "Eye button", detail: "Hide the virtual controls before tapping the settings menus, because the overlay can intercept those taps." },
        { label: "Return to Library", value: "Settings → power icon → Quit", detail: "Save first. Native saves are separate from the original ROM's RetroArch checkpoints; no emulator quicksave shortcut is configured here." }
    ], source: "Ship of Harkinian 9.3.1-android.4 menus and native save/reopen observed on Nova, 10 November 2026. The owner confirmed physical controls and sound. Library Play, loading NOVA, native Quit and responsive Library return passed with the repaired launcher." },
    { match: /^SM64 Coop Deluxe Android 1\.5\.1$/, name: "Mario 64 Coop Deluxe · native", rows: [
        { label: "Play alone", value: "Host → Direct Connection → Host", detail: "The prepared profile has one player and no enabled mods. CoopNet is not needed for this local setup." },
        { label: "Port menu", value: "Start, then R", detail: "Pause first, then open the port menu. The owner confirmed this physical-controller path, movement, jump, camera, sound and touch-button autohide." },
        { label: "Save progress", value: "Use the game's save prompts", detail: "Earned stars and course progress belong to a separate native save slot. Saving and reopening earned progress has not been checked yet; RetroArch checkpoints are not imported." },
        { label: "Exit", value: "Port menu → Stop Hosting → Quit", detail: "Confirm Stop Hosting, then choose Quit from the main menu. Exiting alone does not prove progress was saved. Library Play and normal Quit back to a responsive Library passed with the repaired launcher." }
    ], source: "SM64 Coop Deluxe Android 1.5.1 menus and retained one-player settings observed on Nova, 10 November 2026. Library Play, gameplay, the port menu and normal Quit back to Library passed with the repaired launcher. This is not emulator save-state support." },
    { match: /^DevilutionX Android 1\.5\.5 · shareware$/, name: "Diablo shareware · native", rows: [
        { label: "Game menu", value: "Select + Start", detail: "The owner checked this shortcut on the physical Nova. The touch Menu button also opens it." },
        { label: "Inventory", value: "R2", detail: "Checked by the owner on the physical Nova." },
        { label: "Save / load", value: "Game menu → Save / Load", detail: "The separate Nova warrior was saved, then loaded after a full app restart. Saving is explicit; do it before exiting." },
        { label: "Quit the game", value: "Game menu → Quit Game", detail: "This returns to the title menu. This is the official shareware portion, not the full game or Hellfire. RetroArch quicksave shortcuts do not apply." },
        { label: "Return to Library", value: "Android Home", detail: "Save first, then Quit Game. Android Home returns to Library and leaves the app in the background; it does not quit the process or create a save." }
    ], source: "DevilutionX 1.5.5 native save/reopen observed on Nova and physical controls/sound confirmed by the owner, 10 November 2026. Library Play and loading the Nova hero passed with the repaired launcher. Android Home returned to a responsive Library; this leaves the app in the background." },
    { match: /^HakuX/i, profile: "hakux-nova-v1", name: "HakuX · Nova shortcuts", rows: [
        { label: "Emulator menu", value: "Select + Y / Android Back" },
        { label: "Save checkpoint", value: "Select + R1", detail: "Uses an empty slot first. When all ten slots are full, replacing the selected checkpoint asks for confirmation." },
        { label: "Load checkpoint", value: "Select + L1", detail: "Loads the selected slot. Checkpoint restore still needs checking on your device; use the game's own saves too." },
        { label: "Previous / next slot", value: "Select + L3 / R3", detail: "Changes the selected slot; it does not immediately load it. The slot selection belongs to this game." },
        { label: "Xbox Back", value: "Tap Select", detail: "Hold Select for shortcuts. Controller shortcuts can be turned off in the emulator menu." },
        { label: "Return to Library", value: "Android Back → Exit", detail: "Save in the game or make a checkpoint before exiting. Exit does not promise an automatic save." }
    ], source: "Nova shortcut profile explicitly selected by the catalogue. These controls require the matching HakuX build with shortcuts enabled." },
    { match: /^HakuX/i, name: "HakuX", rows: [
        { label: "Emulator menu", value: "Android Back", detail: "Use the Nova's Android Back button, not the Xbox Back/Select button." },
        { label: "Save checkpoint", value: "Back → Save state", detail: "Choose a slot in HakuX. RetroArch's Select + shoulder shortcuts are not configured in the standard HakuX build." },
        { label: "Load checkpoint", value: "Back → Load state", detail: "Choose a saved slot in HakuX. Restore still needs checking on this device; keep the game's own saves too." },
        { label: "Return to Library", value: "Android Back → Exit", detail: "An external Library launch offers the return-to-frontend action. Save first; exit is not an automatic checkpoint." }
    ], source: "HakuX 1.2 session menu and input handling. A visible save-state menu does not prove a successful restore on this device." },
    { match: /^RetroArch/, name: "RetroArch", rows: [
        { label: "RetroArch menu", value: "Select + Y" },
        { label: "Save checkpoint", value: "Select + R1" },
        { label: "Load checkpoint", value: "Select + L1",
          detail: "Loads the selected slot. Which slot is selected at launch depends on effective RetroArch settings; check the slot, preview and date before loading. This shortcut does not itself confirm that current progress was protected." },
        { label: "Older / newer slot", value: "Select + L3 / R3" },
        { label: "Quit to Library", value: "Select + Start" }
    ], source: "Nova shortcut mapping last checked on 9 October 2026. Current slot selection, core support and effective overrides still need checking in the active runtime." },
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
    { system: "xbox", titles: ["halo", "halo: combat evolved", "halo - combat evolved"], rows: [
        { label: "Move / look", value: "Left / right stick" },
        { label: "Interact", value: "X  (left face button)", detail: "The opening cryo-tube prompt uses X. Later actions are explained by the game's prompts." },
        { label: "Pause", value: "Start" }
    ], tips: [
        { label: "Save in the game", value: "Start → Save and Quit", detail: "Halo's own checkpoint is separate from HakuX save states. Save-and-quit and reopening the tutorial were checked on Nova." }
    ], source: "Halo opening tutorial prompts and pause menu on Nova." },
    { system: "psx", titles: ["metal gear solid"], multiDisc: true, rows: [
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
    ], source: "Controls: Super Mario Wiki's All-Stars control tables." }
];

function emulatorFor(e) {
    var route = e && e.route ? String(e.route).trim() : "";
    for (var i = 0; i < EMULATORS.length; i++)
        if (EMULATORS[i].match.test(route) && (!EMULATORS[i].profile || EMULATORS[i].profile === e.sessionProfile)) return EMULATORS[i];
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
    return !!(e && e.systemId !== "androidapps" && e.systemId !== "emulators");
}

function discRows(e) {
    if(!available(e))return [];
    var game=gameFor(e),explicit=!!(e.discSetId || e.discAliasFor || e.discMembers);
    if(!explicit && !(game && game.multiDisc))return [];
    var out=[{label:"Changing discs",value:"Keep the game running",detail:"A disc opened from Library is a launch request, not a live disc swap. Use the active emulator's disc controls when the game asks. Keep current progress; this help does not create a checkpoint or change a disc."}];
    var emulator=emulatorFor(e);
    if(!emulator || emulator.name!=="RetroArch") {
        out.push({label:"Disc swap controls",value:"Not checked",detail:"The declared route does not identify RetroArch. Return to the running emulator and check its own disc-swap support. No shortcut, playlist contents or save compatibility has been established for this route."});
        return out;
    }
    out.push({label:"Open disc controls",value:"Quick Menu → Disc Control",detail:"In the active RetroArch session, open its menu using your configured menu control. Disc Control depends on the loaded core; a catalogue label does not prove the active core supports it."});
    out.push({label:"If the next disc is listed",value:"Eject → select → insert",detail:"Eject the virtual disc, choose the requested disc in Current Disc Index, then insert it and resume. Match the actual disc label; do not assume an index proves which image is present."});
    out.push({label:"If the disc is not listed",value:"Use the runtime's file selector",detail:"Compatible cores can add an image with Disc Image Append or Load New Disc. Keep the current session. Grouping in Library does not prove a complete M3U was loaded; do not restart or rename memory-card files to guess at a fix."});
    if(game && game.multiDisc)out.push({label:"If MGS still asks for a disc",value:"Let it detect the eject",detail:"Libretro documents an RGUI workaround: select No Disk, briefly return to the game so it detects the empty drive, then return to the menu and select the requested disc. Labels and behaviour can vary by menu and core; this is guidance, not a verified swap here."});
    out.push({label:"Source",value:"Libretro disc-swapping guide",detail:"https://docs.libretro.com/guides/disc-swapping/ · General runtime guidance. Active playlist contents, shared memory-card setup and a successful swap still need checking on the exact device and core."});
    return out;
}

function restoreRows(e) {
    if(!available(e))return [];
    var emu=emulatorFor(e);
    if(emu && emu.name==="RetroArch")return [
        {label:"Before loading",value:"Use a different slot",detail:"Save current progress to a different manual slot and confirm the result before choosing an older state. Do not overwrite your only working copy. A shortcut press alone is not confirmation."},
        {label:"Choose what to load",value:"Review the selected slot",detail:"Use the runtime's slot, preview and date. A quick-load shortcut does not necessarily select the newest state. A different core/version or edition can make a state incompatible; keep both copies."},
        {label:"Undo a load",value:"Undo, if offered",detail:"In Quick Menu, open Undo Load State if offered; some layouts put it under Save States. Core support, menu settings and Hardcore mode can hide it. The backup is in memory, not a durable checkpoint: keep content open and check whether undo actually restored progress. Undo has not been verified on this exact setup."},
        {label:"Source",value:"Pinned RetroArch save/menu code",detail:"https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/tasks/task_save.c · Runtime guidance only. The separate Nova safe-load source guard is not presumed built, installed or active."}
    ];
    return [{label:"Undo after loading",value:emu && emu.name==="HakuX · Nova shortcuts"?"Not in this shortcut profile":"Not checked",detail:"No undo-load path has been verified for this runtime/profile. Check its own support and keep a working save before loading older progress. In-game saves and emulator checkpoints are separate; no automatic backup is implied."}];
}

// Rows for the list panel: section headings are dim; a row's detail shows below the list.
function rows(e) {
    if (!available(e)) return [];
    var out = [], g = gameFor(e), emu = emulatorFor(e);
    // Session controls come first, so saving never sits below a long game guide.
    if (emu) {
        out.push({ label: emu.name, value: "", dim: true, detail: emu.source });
        emu.rows.forEach(function(r) { out.push(r); });
    } else {
        out.push({ label: "Emulator controls", value: "Not checked", detail: "The catalogue does not identify a supported emulator route. Check its own controls before relying on a save/load shortcut." });
    }
    out.push({label:"Loading and undo",value:"",dim:true,detail:"Review the current runtime before replacing a running state. This guide never executes a save or load."});
    restoreRows(e).forEach(function(row){out.push(row);});
    discRows(e).forEach(function(row){out.push(row);});
    if (g) {
        if (g.tips.length) {
            out.push({ label: "Saving in the game", value: "", dim: true, detail: "Game saves and emulator checkpoints are separate. Highlight a row to read it." });
            g.tips.forEach(function(r) { out.push(r); });
        }
        out.push({ label: "In the game", value: "", dim: true, detail: g.source });
        g.rows.forEach(function(r) { out.push(r); });
    }
    return out;
}

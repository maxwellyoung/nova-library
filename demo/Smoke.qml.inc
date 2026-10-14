    Timer {
        interval: 1500; running: true; repeat: false
        function require(value, reason) { if (!value) throw new Error(reason); }
        function key(ui, value) { ui.handleKey({key:value, isAutoRepeat:false, accepted:false}); }
        onTriggered: {
            try {
                require(themeLoader.status === Loader.Ready, "theme loader failed");
                var ui=themeLoader.item;
                require(ui.rawEntries.length === 4, "synthetic catalogue mismatch");
                ui.switchView("home");
                key(ui,Qt.Key_Right); key(ui,Qt.Key_Left);
                var pinCount=ui.pins.length;
                key(ui,Qt.Key_Y);
                require(ui.pins.length !== pinCount, "Y did not toggle keep");
                key(ui,Qt.Key_X);
                require(ui.overlay === "details", "X did not open details");
                key(ui,Qt.Key_Escape);
                require(ui.overlay === "", "Escape did not close details");
                key(ui,Qt.Key_Return);
                require(!ui.current.launchable, "demo became launchable");
                require(ui.overlay === "details", "unavailable Enter did not explain route");
                key(ui,Qt.Key_Escape);
                key(ui,Qt.Key_PageDown);
                require(ui.view === "library", "PageDown did not switch views");
                key(ui,Qt.Key_Down); key(ui,Qt.Key_Up); key(ui,Qt.Key_Right); key(ui,Qt.Key_Left);
                ui.zone="content";
                key(ui,Qt.Key_Home); key(ui,Qt.Key_End); key(ui,Qt.Key_Return);
                require(ui.overlay === "details", "Library unavailable Enter failed");
                key(ui,Qt.Key_Escape);
                key(ui,Qt.Key_X);
                require(ui.overlay === "details", "Library X failed");
                key(ui,Qt.Key_Escape); key(ui,Qt.Key_Y);
                key(ui,Qt.Key_PageDown);
                require(ui.view === "consoles", "Consoles view failed");
                key(ui,Qt.Key_Right); key(ui,Qt.Key_Left); key(ui,Qt.Key_Down); key(ui,Qt.Key_Up);
                ui.zone="content";
                key(ui,Qt.Key_Return);
                require(ui.view === "library" && ui.filters.system !== "", "console filtering failed");
                key(ui,Qt.Key_Escape);
                require(ui.view === "consoles", "console return failed");
                key(ui,Qt.Key_PageUp);
                require(ui.view === "library", "PageUp failed");
                console.log("NOVA_DEMO_SMOKE_PASS: keyboard actions, keep/details, console filter and return.");
                Qt.exit(0);
            } catch(error) {
                console.error("NOVA_DEMO_SMOKE_FAIL: " + error);
                Qt.exit(1);
            }
        }
    }

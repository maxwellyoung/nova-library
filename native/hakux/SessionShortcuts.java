package com.rfandango.haku_x;

import java.util.HashSet;
import java.util.Set;

/** Android-key state machine; the activity owns device validation and actions. */
public final class SessionShortcuts {
    public static final int NONE = 0, SAVE = 1, LOAD = 2, PREVIOUS = 3, NEXT = 4, MENU = 5;
    public static final int SELECT = 109;
    private int modifierDevice = -1;
    private boolean modifierUsed;
    private final Set<String> consumed = new HashSet<>();

    public static final class Result {
        public final boolean handled, tapSelect;
        public final int action;
        Result(boolean handled, boolean tapSelect, int action) {
            this.handled = handled;
            this.tapSelect = tapSelect;
            this.action = action;
        }
    }

    private static final Result PASS = new Result(false, false, NONE);
    private static final Result HELD = new Result(true, false, NONE);

    public Result key(int device, int code, boolean down, int repeat, boolean canceled) {
        if (code == SELECT) {
            if (down) {
                if (modifierDevice == -1 && repeat == 0 && !canceled) {
                    modifierDevice = device;
                    modifierUsed = false;
                    return HELD;
                }
                return modifierDevice == device ? HELD : PASS;
            }
            if (modifierDevice != device) return PASS;
            boolean tap = !modifierUsed && !canceled;
            modifierDevice = -1;
            return new Result(true, tap, NONE);
        }

        String token = device + ":" + code;
        if (consumed.contains(token)) {
            if (!down) consumed.remove(token);
            return HELD;
        }
        if (modifierDevice != device) return PASS;
        // Releasing a key pressed before Select must still reach the game.
        if (!down) return PASS;
        modifierUsed = true;
        int action;
        switch (code) {
            case 103: action = SAVE; break;     // R1
            case 102: action = LOAD; break;     // L1
            case 106: action = PREVIOUS; break; // L3
            case 107: action = NEXT; break;     // R3
            case 100: action = MENU; break;     // Y
            default: return PASS;
        }
        consumed.add(token);
        return new Result(true, false, repeat == 0 && !canceled ? action : NONE);
    }

    /** Focus loss/disconnect must never leave a held modifier behind. */
    public void reset() {
        modifierDevice = -1;
        modifierUsed = false;
        consumed.clear();
    }
}

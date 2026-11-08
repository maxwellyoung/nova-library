package com.rfandango.haku_x;

import java.util.Arrays;
import org.junit.Test;
import static org.junit.Assert.*;

public class SessionShortcutsTest {
    private final SessionShortcuts keys = new SessionShortcuts();
    private SessionShortcuts.Result down(int code) { return keys.key(1, code, true, 0, false); }
    private SessionShortcuts.Result up(int code) { return keys.key(1, code, false, 0, false); }

    @Test public void chordDoesNotLeakBackOrRepeatSave() {
        assertTrue(down(109).handled);
        assertEquals(SessionShortcuts.SAVE, down(103).action);
        assertEquals(SessionShortcuts.NONE, keys.key(1,103,true,3,false).action);
        assertTrue(up(103).handled);
        assertFalse(up(109).tapSelect);
        assertFalse(down(103).handled);
    }
    @Test public void tapSelectIsReplayedOnlyAfterCleanRelease() {
        down(109);
        assertTrue(up(109).tapSelect);
        down(109);
        assertFalse(keys.key(1,109,false,0,true).tapSelect);
    }
    @Test public void shoulderReleaseAfterModifierReleaseStaysConsumed() {
        down(109); down(102); up(109);
        assertTrue(up(102).handled);
        assertFalse(up(102).handled);
    }
    @Test public void anotherPlayersShoulderCannotTriggerOrReleaseTheModifier() {
        down(109);
        assertFalse(keys.key(2,103,true,0,false).handled);
        assertFalse(keys.key(2,109,false,0,false).handled);
        assertEquals(SessionShortcuts.LOAD, down(102).action);
    }
    @Test public void anotherPlayersSelectRemainsAnOrdinaryGameButton() {
        down(109);
        assertFalse(keys.key(2,109,true,0,false).handled);
        assertFalse(keys.key(2,109,false,0,false).handled);
        assertTrue(up(109).tapSelect);
    }
    @Test public void focusLossOrDisconnectCannotLeaveActionsArmed() {
        down(109); keys.reset();
        assertFalse(down(103).handled);
        assertFalse(up(109).tapSelect);
        down(109); down(103); keys.reset();
        assertFalse(up(103).handled);
        assertEquals(SessionShortcuts.NONE, down(102).action);
    }
    @Test public void canceledAndOrphanedRepeatsNeverLoad() {
        down(109);
        assertEquals(SessionShortcuts.NONE, keys.key(1,102,true,0,true).action);
        up(102);
        assertEquals(SessionShortcuts.NONE, keys.key(1,102,true,4,false).action);
        assertFalse(up(109).tapSelect);
    }
    @Test public void aShoulderPressedBeforeSelectStillGetsItsRelease() {
        assertFalse(down(102).handled);
        down(109);
        assertFalse(up(102).handled);
    }
    @Test public void ordinaryGameInputIsNotConsumedAndDoesNotReplaySelect() {
        assertFalse(down(96).handled);
        down(109);
        assertFalse(down(96).handled);
        assertFalse(up(109).tapSelect);
    }
    @Test public void slotAndMenuBindingsKeepTheEstablishedPositions() {
        down(109);
        assertEquals(SessionShortcuts.PREVIOUS, down(106).action); up(106);
        assertEquals(SessionShortcuts.NEXT, down(107).action); up(107);
        assertEquals(SessionShortcuts.MENU, down(100).action); up(100);
        assertFalse(up(109).tapSelect);
    }
    @Test public void quickSavePreservesOccupiedSlotsAndWrapsIntoAHole() {
        assertEquals(1, CheckpointSlots.emptyAtOrAfter(10,10,Arrays.asList(10,2,3)));
        assertEquals(4, CheckpointSlots.emptyAtOrAfter(2,10,Arrays.asList(2,3,5)));
        assertEquals(0, CheckpointSlots.emptyAtOrAfter(3,3,Arrays.asList(1,2,3)));
    }
    @Test(expected = IllegalArgumentException.class) public void malformedSlotCannotBeSelected() {
        CheckpointSlots.emptyAtOrAfter(0,10,Arrays.asList(1));
    }
}

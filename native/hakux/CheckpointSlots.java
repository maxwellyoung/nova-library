package com.rfandango.haku_x;

import java.util.Collection;

/** A quick save only chooses an empty slot; 0 requests explicit replacement. */
public final class CheckpointSlots {
    private CheckpointSlots() {}

    public static int emptyAtOrAfter(int selected, int count, Collection<Integer> occupied) {
        if (count < 1 || selected < 1 || selected > count) throw new IllegalArgumentException("Invalid slot range");
        for (int offset = 0; offset < count; offset++) {
            int candidate = (selected - 1 + offset) % count + 1;
            if (!occupied.contains(candidate)) return candidate;
        }
        return 0;
    }
}

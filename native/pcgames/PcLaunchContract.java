// SPDX-License-Identifier: GPL-3.0-or-later
package org.pegasus_frontend.android;

/** Allowlisted public launch protocols; no paths, command lines or configuration extras. */
public final class PcLaunchContract {
    private PcLaunchContract() {}
    public static String packageName(String id) {
        if ("droiddeck".equals(id)) return "com.droiddeck.launcher";
        if ("gamenative".equals(id)) return "app.gamenative";
        return null;
    }
    public static String activity(String id) {
        if ("droiddeck".equals(id)) return "com.droiddeck.launcher.FrontEndActivity";
        if ("gamenative".equals(id)) return "app.gamenative.MainActivity";
        return null;
    }
    public static String action(String id) {
        String name=packageName(id);return name==null?null:name+".LAUNCH_GAME";
    }
    public static boolean supported(String id,String version) {
        return "droiddeck".equals(id) && "0.7.0".equals(version)
            || "gamenative".equals(id) && "1.4.0".equals(version);
    }
}

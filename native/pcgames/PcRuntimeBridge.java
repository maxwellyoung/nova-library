// SPDX-License-Identifier: GPL-3.0-or-later
package org.pegasus_frontend.android;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import org.json.JSONArray;
import org.json.JSONObject;

/** Called on Android's UI thread. Queries exactly two apps and stores nothing. */
public final class PcRuntimeBridge {
    private PcRuntimeBridge() {}
    private static JSONObject state(Activity activity,String id) throws Exception {
        JSONObject value=new JSONObject();value.put("id",id);value.put("available",false);value.put("version","");
        if (activity==null) return value;
        try {
            PackageManager manager=activity.getPackageManager();String name=PcLaunchContract.packageName(id);
            PackageInfo app=manager.getPackageInfo(name,0);
            ActivityInfo entry=manager.getActivityInfo(new ComponentName(name,PcLaunchContract.activity(id)),0);
            value.put("version",app.versionName==null?"":app.versionName);
            value.put("available",app.applicationInfo!=null && app.applicationInfo.enabled && entry.enabled && entry.exported);
        } catch (PackageManager.NameNotFoundException | SecurityException ignored) { }
        return value;
    }
    public static String inspect(Activity activity) {
        try {return new JSONArray().put(state(activity,"droiddeck")).put(state(activity,"gamenative")).toString();}
        catch (Exception ignored) {return "[]";}
    }
    private static boolean foreground(Activity activity) {
        return activity!=null && !activity.isFinishing() && !activity.isDestroyed() && activity.hasWindowFocus();
    }
    private static String reply(boolean accepted,String code) {
        try {return new JSONObject().put("accepted",accepted).put("code",code).toString();}
        catch (Exception ignored) {return "{}";}
    }
    public static String openGame(Activity activity,String id,int appId,String expectedVersion) {
        if (appId<=0 || !PcLaunchContract.supported(id,expectedVersion)) return reply(false,"invalid-request");
        if (!foreground(activity)) return reply(false,"not-foreground");
        try {
            JSONObject current=state(activity,id);
            if (!expectedVersion.equals(current.optString("version"))) return reply(false,"version-changed");
            if (!current.optBoolean("available")) return reply(false,"unavailable");
            Intent request=new Intent(PcLaunchContract.action(id));
            request.setComponent(new ComponentName(PcLaunchContract.packageName(id),PcLaunchContract.activity(id)));
            request.putExtra("app_id",appId);request.putExtra("game_source","STEAM");
            if (!foreground(activity)) return reply(false,"not-foreground");
            activity.startActivity(request);
            return reply(true,"dispatched");
        } catch (Exception ignored) {return reply(false,"dispatch-failed");}
    }
}

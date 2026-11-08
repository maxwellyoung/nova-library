package android.content; public class Context {
 public static final String ACCESSIBILITY_SERVICE="accessibility";
 public final android.view.accessibility.AccessibilityManager manager=new android.view.accessibility.AccessibilityManager();
 public Object getSystemService(String name){return manager;}
}

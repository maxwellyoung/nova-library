package android.view.accessibility; import java.util.*; public class AccessibilityManager {
 public interface TouchExplorationStateChangeListener {void onTouchExplorationStateChanged(boolean b);}
 public final List<TouchExplorationStateChangeListener> listeners=new ArrayList<>();
 public boolean enabled,register=true;
 public boolean isTouchExplorationEnabled(){return enabled;}
 public boolean addTouchExplorationStateChangeListener(TouchExplorationStateChangeListener l){if(register)listeners.add(l);return register;}
 public boolean removeTouchExplorationStateChangeListener(TouchExplorationStateChangeListener l){return listeners.remove(l);}
 public void set(boolean b){enabled=b;for(TouchExplorationStateChangeListener l:new ArrayList<>(listeners))l.onTouchExplorationStateChanged(b);}
}

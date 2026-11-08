package android.view; import java.util.*; public class ViewTreeObserver {
 public interface OnGlobalLayoutListener {void onGlobalLayout();}
 public final List<OnGlobalLayoutListener> listeners=new ArrayList<>();
 public void addOnGlobalLayoutListener(OnGlobalLayoutListener l){listeners.add(l);}
 public void removeOnGlobalLayoutListener(OnGlobalLayoutListener l){listeners.remove(l);}
 public boolean isAlive(){return true;}
 public void dispatch(){for(OnGlobalLayoutListener l:new ArrayList<>(listeners))l.onGlobalLayout();}
}

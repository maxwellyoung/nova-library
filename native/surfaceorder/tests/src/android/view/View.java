package android.view; public class View {
 public static final int NO_ID=-1; public int id=NO_ID; public Object background,foreground;
 public static class AccessibilityDelegate {} public AccessibilityDelegate delegate;
 public AccessibilityDelegate getAccessibilityDelegate(){return delegate;}
 public int getId(){return id;} public Object getBackground(){return background;} public Object getForeground(){return foreground;}
 public final android.content.Context context=new android.content.Context(); public android.content.Context getContext(){return context;}
 public int left,top,width=1280,height=960; private final ViewTreeObserver observer=new ViewTreeObserver();
 public int getLeft(){return left;} public int getTop(){return top;} public int getWidth(){return width;} public int getHeight(){return height;}
 public ViewTreeObserver getViewTreeObserver(){return observer;}
}

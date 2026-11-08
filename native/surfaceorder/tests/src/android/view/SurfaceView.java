package android.view; import java.util.*; public class SurfaceView extends View {
 public boolean onTop; public final List<Boolean> requests=new ArrayList<>();
 public void setZOrderOnTop(boolean b){requests.add(b);onTop=b;}
}

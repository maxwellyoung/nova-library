package android.view; import java.util.*; public class ViewGroup extends View {
 public final List<View> children=new ArrayList<>(); public int getChildCount(){return children.size();}
 public View getChildAt(int i){return children.get(i);} public void add(View v){children.add(v);} public void remove(View v){children.remove(v);}
}

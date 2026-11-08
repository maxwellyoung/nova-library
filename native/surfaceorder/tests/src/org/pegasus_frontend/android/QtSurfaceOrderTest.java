package org.pegasus_frontend.android;
import android.view.*; import org.qtproject.qt5.android.*;
public class QtSurfaceOrderTest {
 static int checks;
 static void check(boolean value,String why){++checks;if(!value)throw new AssertionError(why);}
 static void layout(QtLayout q){q.getViewTreeObserver().dispatch();}
 public static void main(String[] args){
  QtSurfaceOrder policy=new QtSurfaceOrder(); ViewGroup content=new ViewGroup(); QtLayout q=new QtLayout(); content.add(q);
  policy.bind(content,true); check(q.getViewTreeObserver().listeners.size()==1,"bind once");
  policy.bind(content,true); check(q.getViewTreeObserver().listeners.size()==1,"repeated bind preserves single observer");
  final int[] other={0}; q.getViewTreeObserver().addOnGlobalLayoutListener(()->++other[0]);
  QtSurface first=new QtSurface();q.add(first);layout(q);
  check(first.onTop,"new primary surface raised on traversal"); check(other[0]==1,"existing observer retained");
  layout(q);check(first.requests.size()==1,"stable traversal does not repeat setter");
  QtEditText input=new QtEditText();q.add(input);layout(q);check(first.onTop,"nondrawing input proxy allowed");
  View host=new View();host.delegate=new org.qtproject.qt5.android.accessibility.QtAccessibilityDelegate();q.add(host);layout(q);
  check(first.onTop,"exact transparent Qt accessibility host allowed");
  q.context.manager.set(true);check(!first.onTop,"exploration event restores ordinary order without layout");
  q.context.manager.set(false);check(first.onTop,"exploration disabled event reapplies guarded bypass");
  check(host.delegate.getClass()==org.qtproject.qt5.android.accessibility.QtAccessibilityDelegate.class,"delegate unchanged");
  host.background=new Object();layout(q);check(!first.onTop,"accessibility host background blocks");
  host.background=null;host.foreground=new Object();layout(q);check(!first.onTop,"accessibility host foreground blocks");
  host.foreground=null;host.id=7;layout(q);check(!first.onTop,"unexpected accessibility host ID blocks");
  host.id=View.NO_ID;host.width=1200;layout(q);check(!first.onTop,"partial accessibility host blocks");
  host.width=q.width;host.delegate=new View.AccessibilityDelegate();layout(q);check(!first.onTop,"other accessibility delegate blocks");
  host.delegate=new org.qtproject.qt5.android.accessibility.QtAccessibilityDelegate(){};layout(q);check(!first.onTop,"delegate subclass blocks");
  host.delegate=new org.qtproject.qt5.android.accessibility.QtAccessibilityDelegate();layout(q);check(first.onTop,"restored exact host allowed");
  q.remove(host);layout(q);check(first.onTop,"accessibility host removed safely");
  View overlay=new View();q.add(overlay);layout(q);check(!first.onTop,"native overlay restores ordinary order");
  q.remove(overlay);layout(q);check(first.onTop,"overlay removal restores sole surface bypass");
  QtSurface second=new QtSurface();q.add(second);layout(q);check(!first.onTop&&!second.onTop,"multiple surfaces stay ordinary");
  q.remove(first);layout(q);check(second.onTop,"replacement surface raised");
  check(first.requests.get(first.requests.size()-1)==false,"old surface restored");
  second.width=1200;layout(q);check(!second.onTop,"partial-size surface stays ordinary");
  second.width=q.width;second.left=1;layout(q);check(!second.onTop,"offset surface stays ordinary");
  second.left=0;layout(q);check(second.onTop,"full-layout geometry restored");
  QtLayout recreated=new QtLayout();QtSurface third=new QtSurface();recreated.add(third);
  content.remove(q);content.add(recreated);policy.bind(content,true);
  check(!second.onTop&&third.onTop,"recreated layout restores old and binds new");
  check(q.getViewTreeObserver().listeners.size()==1,"old policy observer removed; other observer retained");
  check(q.context.manager.listeners.isEmpty(),"old accessibility state listener removed");
  check(recreated.getViewTreeObserver().listeners.size()==1,"new layout observer bound once");
  policy.bind(content,false);check(!third.onTop,"unsupported runtime restores order");
  check(recreated.getViewTreeObserver().listeners.isEmpty(),"unsupported runtime unbound");
  check(recreated.context.manager.listeners.isEmpty(),"unsupported runtime state listener removed");
  policy.bind(content,true);check(third.onTop,"supported rebind");
  policy.close();policy.close();check(!third.onTop,"close idempotently restores order");
  check(recreated.getViewTreeObserver().listeners.isEmpty(),"close removes observer");
  check(recreated.context.manager.listeners.isEmpty(),"close removes accessibility state listener");
  recreated.context.manager.register=false;policy.bind(content,true);check(!third.onTop,"failed state listener registration blocks");policy.close();
  QtLayout extra=new QtLayout();content.add(extra);policy.bind(content,true);
  check(!third.onTop&&recreated.getViewTreeObserver().listeners.isEmpty(),"ambiguous root layouts not changed");
  System.out.println(checks+" surface-order lifecycle checks passed");
 }
}

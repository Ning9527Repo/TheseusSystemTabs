#import "Host.h"
#import "WeChatHost.h"
#import <objc/runtime.h>
#import <objc/message.h>
#import <dispatch/dispatch.h>
#import <string.h>

@implementation NGWeChatTabEntry
@end
@implementation NGWeChatTabSnapshot
@end

@interface NGWeChatTabsBridge : NSObject
+ (void)update:(UIView *)bar;
+ (void)detach:(UIView *)bar;
+ (BOOL)usesOverlay:(UIView *)bar;
@end

BOOL NGIsWeChatProcess(void) {
    static BOOL result;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        NSBundle *main = NSBundle.mainBundle;
        // The clone has a distinct identifier; require the WeChat executable too.
        result = [main.bundlePath.pathExtension isEqualToString:@"app"] &&
            [main.infoDictionary[@"CFBundleExecutable"] isEqualToString:@"WeChat"] &&
            [main.bundleIdentifier hasPrefix:@"com.tencent."];
    });
    return result;
}

static BOOL NGWCIsClass(id object, const char *name) {
    for (Class cls = object_getClass(object); cls; cls = class_getSuperclass(cls)) {
        if (!strcmp(class_getName(cls), name)) return YES;
    }
    return NO;
}

static Method NGWCMethod(id object, SEL selector, unsigned args, char type) {
    if (!object) return NULL;
    Method method = class_getInstanceMethod(object_getClass(object), selector);
    if (!method || method_getNumberOfArguments(method) != args) return NULL;
    char ret[128] = {0};
    method_getReturnType(method, ret, sizeof(ret));
    return ret[0] == type ? method : NULL;
}

static id NGWCObject(id object, const char *name) {
    SEL sel = sel_registerName(name);
    return NGWCMethod(object, sel, 2, '@') ? ((id (*)(id, SEL))objc_msgSend)(object, sel) : nil;
}

static id NGWCIvar(id object, const char *name) {
    Ivar ivar = object ? class_getInstanceVariable(object_getClass(object), name) : NULL;
    const char *type = ivar ? ivar_getTypeEncoding(ivar) : NULL;
    return type && type[0] == '@' ? object_getIvar(object, ivar) : nil;
}

static BOOL NGWCBool(id object, const char *name, BOOL fallback) {
    SEL sel = sel_registerName(name);
    if (NGWCMethod(object, sel, 2, 'B') || NGWCMethod(object, sel, 2, 'c')) {
        return ((BOOL (*)(id, SEL))objc_msgSend)(object, sel);
    }
    return fallback;
}

static NSInteger NGWCIndex(id object, const char *name, NSInteger fallback) {
    SEL sel = sel_registerName(name);
    if (NGWCMethod(object, sel, 2, 'Q') || NGWCMethod(object, sel, 2, 'q')) {
        return ((NSInteger (*)(id, SEL))objc_msgSend)(object, sel);
    }
    return fallback;
}

static NSArray *NGWCArray(id value) { return [value isKindOfClass:NSArray.class] ? value : nil; }
static NSString *NGWCString(id value) {
    if ([value isKindOfClass:NSString.class]) return value;
    if ([value isKindOfClass:NSNumber.class]) return [value stringValue];
    return nil;
}
static UIImage *NGWCImage(id value) { return [value isKindOfClass:UIImage.class] ? value : nil; }
static UIColor *NGWCColor(id value) { return [value isKindOfClass:UIColor.class] ? value : nil; }

static id NGWCItemView(UIView *bar, NSInteger index) {
    SEL sel = sel_registerName("tabBarItemViewAtIndex:");
    Method method = NGWCMethod(bar, sel, 3, '@');
    if (!method) return nil;
    char arg[32] = {0}; method_getArgumentType(method, 2, arg, sizeof(arg));
    if (arg[0] != 'q' && arg[0] != 'Q') return nil;
    id result = ((id (*)(id, SEL, NSInteger))objc_msgSend)(bar, sel, index);
    return [result isKindOfClass:UIView.class] ? result : nil;
}

static UIImage *NGWCDisplayedImage(UIView *view) {
    NSMutableArray<UIView *> *queue = [view.subviews mutableCopy];
    for (NSUInteger i = 0; i < queue.count && i < 40; i++) {
        UIView *v = queue[i];
        if ([NSStringFromClass(object_getClass(v)) rangeOfString:@"badge" options:NSCaseInsensitiveSearch].location != NSNotFound) continue;
        if ([v isKindOfClass:UIImageView.class]) {
            UIImage *image = ((UIImageView *)v).image;
            if (image && image.size.width > 0 && image.size.width <= 96 && image.size.height > 0 && image.size.height <= 96) return image;
        }
        if (queue.count + v.subviews.count <= 40) [queue addObjectsFromArray:v.subviews];
    }
    return nil;
}

static id NGWCOwner(UIView *bar, BOOL modern) {
    for (UIResponder *v = bar.nextResponder; v; v = v.nextResponder) {
        if (modern && NGWCIsClass(v, "NewMainTabBarViewController") && NGWCIvar(v, "_tabBarView") == bar) return v;
        if (!modern && NGWCIsClass(v, "MainTabBarViewController") && NGWCObject(v, "tabBar") == bar) return v;
        if ([v isKindOfClass:UIWindow.class]) break;
    }
    return nil;
}

NGWeChatTabSnapshot *NGWeChatCopyTabs(UIView *bar) {
    if (!NSThread.isMainThread || !NGIsWeChatProcess() || !bar.window) return nil;
    BOOL modern = NGWCIsClass(bar, "WCTabBarView");
    if (!modern && !NGWCIsClass(bar, "MMTabBar")) return nil;
    if (!NGWCOwner(bar, modern)) return nil;
    if (modern && !NGWCObject(bar, "itemSelectionHandler")) return nil;
    NSArray *models = NGWCArray(NGWCObject(bar, modern ? "tabItems" : "items"));
    if (models.count != 4) return nil;
    NSInteger selected = modern ? NGWCIndex(bar, "selectedIndex", -1) : -1;
    id selectedItem = modern ? nil : NGWCObject(bar, "selectedItem");
    NSMutableArray<NGWeChatTabEntry *> *entries = [NSMutableArray arrayWithCapacity:4];
    for (NSInteger i = 0; i < 4; i++) {
        UIView *view = NGWCItemView(bar, i);
        if (!view || CGRectIsEmpty(view.bounds)) return nil;
        if (modern && (![view isKindOfClass:UIControl.class] || ((UIControl *)view).tag != i)) return nil;
        if (modern && !NGWCMethod(bar, sel_registerName("onItemViewTouchUpInside:"), 3, 'v')) return nil;
        id model = modern ? models[(NSUInteger)i] : (NGWCObject(view, "item") ?: models[(NSUInteger)i]);
        id legacy = modern ? NGWCObject(view, "legacyItem") : model;
        NGWeChatTabEntry *item = [NGWeChatTabEntry new];
        item.identity = model;
        item.title = NGWCString(NGWCObject(model, "title")) ?: NGWCString(NGWCObject(model, "normalTitle"));
        UILabel *label = NGWCObject(view, "titleLabel") ?: NGWCIvar(view, "_textLabel");
        if (!item.title.length && [label isKindOfClass:UILabel.class]) item.title = label.text;
        item.image = NGWCImage(NGWCObject(model, "image")) ?: NGWCImage(NGWCObject(model, "normalImage"));
        item.selectedImage = NGWCImage(NGWCObject(model, "selectedImage")) ?: NGWCImage(NGWCObject(model, "highlightImage"));
        if (!item.image) item.image = NGWCImage(NGWCObject(legacy, "normalImage"));
        if (!item.selectedImage) item.selectedImage = NGWCImage(NGWCObject(legacy, "highlightImage"));
        UIImage *displayed = (!item.image || !item.selectedImage) ? NGWCDisplayedImage(view) : nil;
        if (!item.image) item.image = displayed ?: item.selectedImage;
        if (!item.selectedImage) item.selectedImage = displayed ?: item.image;
        item.badge = NGWCString(NGWCObject(model, "badgeValue")) ?: NGWCString(NGWCObject(view, "badgeString"));
        NSInteger unread = NGWCIndex(view, "unreadCount", 0);
        if (!item.badge.length && unread > 0) item.badge = unread > 99 ? @"99+" : [@(unread) stringValue];
        if ([item.badge isEqualToString:@"0"]) item.badge = nil;
        UIView *badge = NGWCObject(view, "badgeView");
        item.redDot = NGWCBool(model, "showsRedDot", NO) ||
            (!modern && [badge isKindOfClass:UIView.class] && !badge.hidden && !item.badge.length && unread == 0);
        item.enabled = NGWCBool(model, "isEnabled", NGWCBool(model, "enabled", YES)) && NGWCBool(view, "isEnabled", YES);
        item.label = NGWCString(NGWCObject(model, "accessibilityLabel")) ?: view.accessibilityLabel;
        item.selectedColor = NGWCColor(NGWCObject(model, "selectedTitleColor")) ?: NGWCColor(NGWCObject(legacy, "selectedTitleColor"));
        item.normalColor = NGWCColor(NGWCObject(model, "titleColor")) ?: NGWCColor(NGWCObject(model, "normalTitleColor"));
        if (!item.title.length || (!item.image && !item.selectedImage)) return nil;
        if (!modern && models[(NSUInteger)i] == selectedItem) selected = i;
        [entries addObject:item];
    }
    if (selected < 0 || selected >= 4) return nil;
    NGWeChatTabSnapshot *snapshot = [NGWeChatTabSnapshot new];
    snapshot.entries = entries;
    snapshot.selectedIndex = selected;
    return snapshot;
}

NSInteger NGWeChatActivateTab(UIView *bar, NSInteger index) {
    if (!NSThread.isMainThread || index < 0 || index >= 4 || !bar.window) return -1;
    NGWeChatTabSnapshot *before = NGWeChatCopyTabs(bar);
    if (!before || !before.entries[(NSUInteger)index].enabled) return -1;
    id control = NGWCItemView(bar, index);
    if (NGWCIsClass(bar, "WCTabBarView") && [control isKindOfClass:UIControl.class]) {
        SEL sel = sel_registerName("onItemViewTouchUpInside:");
        Method method = NGWCMethod(bar, sel, 3, 'v');
        char arg[32] = {0};
        if (method) method_getArgumentType(method, 2, arg, sizeof(arg));
        if (!method || arg[0] != '@' || ((UIControl *)control).tag != index) return -1;
        ((void (*)(id, SEL, id))objc_msgSend)(bar, sel, control);
    } else {
        // Legacy MMTabBar selection must pass the owning controller's delegate.
        UIResponder *responder = NGWCOwner(bar, NO);
        if (![responder isKindOfClass:UITabBarController.class]) return -1;
        UITabBarController *controller = (UITabBarController *)responder;
        if (controller.tabBar != bar || controller.viewControllers.count != 4) return -1;
        UIViewController *target = controller.viewControllers[(NSUInteger)index];
        id<UITabBarControllerDelegate> delegate = controller.delegate;
        if ([delegate respondsToSelector:@selector(tabBarController:shouldSelectViewController:)] &&
            ![delegate tabBarController:controller shouldSelectViewController:target]) return before.selectedIndex;
        controller.selectedIndex = (NSUInteger)index;
        if (controller.selectedViewController == target &&
            [delegate respondsToSelector:@selector(tabBarController:didSelectViewController:)]) {
            [delegate tabBarController:controller didSelectViewController:target];
        }
    }
    NGWeChatTabSnapshot *after = NGWeChatCopyTabs(bar);
    return after ? after.selectedIndex : -1;
}

typedef struct {
    const char *name;
    Class cls;
    IMP layout;
    IMP window;
    IMP selected;
    IMP hidden;
    IMP alpha;
    IMP hit;
} NGWCSlot;
static NGWCSlot NGWCSlots[2] = {{.name = "MMTabBar"}, {.name = "WCTabBarView"}};

static NGWCSlot *NGWCSlotFor(id object) {
    for (Class cls = object_getClass(object); cls; cls = class_getSuperclass(cls)) {
        for (NSUInteger i = 0; i < 2; i++) if (NGWCSlots[i].cls == cls) return &NGWCSlots[i];
    }
    return NULL;
}

static void NGWCRefresh(UIView *bar) {
    if (NSThread.isMainThread && !NGSystemTabIsCapturing()) [NGWeChatTabsBridge update:bar];
}
static void NGWCLayout(UIView *bar, SEL cmd) {
    NGWCSlot *slot = NGWCSlotFor(bar);
    if (slot && slot->layout) ((void (*)(id, SEL))slot->layout)(bar, cmd);
    NGWCRefresh(bar);
}
static void NGWCWindow(UIView *bar, SEL cmd) {
    NGWCSlot *slot = NGWCSlotFor(bar);
    if (slot && slot->window) ((void (*)(id, SEL))slot->window)(bar, cmd);
    if (!bar.window) [NGWeChatTabsBridge detach:bar];
    else NGWCRefresh(bar);
}
static void NGWCSelected(UIView *bar, SEL cmd, NSUInteger selected) {
    NGWCSlot *slot = NGWCSlotFor(bar);
    if (slot && slot->selected) ((void (*)(id, SEL, NSUInteger))slot->selected)(bar, cmd, selected);
    NGWCRefresh(bar);
}
static void NGWCHidden(UIView *bar, SEL cmd, BOOL hidden) {
    // The native bar is already masked. Capture exclusion must not notify the
    // WeChat controller that the user/navigation has hidden its real tab bar.
    if (NSThread.isMainThread && NGSystemTabIsCapturing() && [NGWeChatTabsBridge usesOverlay:bar]) return;
    NGWCSlot *slot = NGWCSlotFor(bar);
    if (slot && slot->hidden) ((void (*)(id, SEL, BOOL))slot->hidden)(bar, cmd, hidden);
    NGWCRefresh(bar);
}
static void NGWCAlpha(UIView *bar, SEL cmd, CGFloat alpha) {
    NGWCSlot *slot = NGWCSlotFor(bar);
    if (slot && slot->alpha) ((void (*)(id, SEL, CGFloat))slot->alpha)(bar, cmd, alpha);
    NGWCRefresh(bar);
}
static UIView *NGWCHit(UIView *bar, SEL cmd, CGPoint point, UIEvent *event) {
    NGWCSlot *slot = NGWCSlotFor(bar);
    if (NSThread.isMainThread && [NGWeChatTabsBridge usesOverlay:bar]) return nil;
    return slot && slot->hit ? ((UIView *(*)(id, SEL, CGPoint, UIEvent *))slot->hit)(bar, cmd, point, event) : nil;
}

static BOOL NGWCInstall(Class cls, SEL sel, IMP replacement, IMP *original, unsigned args, char ret, const char *arg2) {
    if (*original) return YES;
    Method method = class_getInstanceMethod(cls, sel);
    if (!method || method_getNumberOfArguments(method) != args) return NO;
    char value[128] = {0}; method_getReturnType(method, value, sizeof(value));
    if (value[0] != ret) return NO;
    if (arg2) {
        method_getArgumentType(method, 2, value, sizeof(value));
        if (!strchr(arg2, value[0])) return NO;
    }
    if (args == 4) {
        method_getArgumentType(method, 2, value, sizeof(value));
        if (strcmp(value, @encode(CGPoint))) return NO;
        method_getArgumentType(method, 3, value, sizeof(value));
        if (value[0] != '@') return NO;
    }
    *original = method_getImplementation(method);
    if (!*original || *original == replacement) { *original = NULL; return NO; }
    if (!class_addMethod(cls, sel, replacement, method_getTypeEncoding(method))) {
        *original = method_setImplementation(method, replacement);
    }
    return YES;
}

static void NGWCInstallClasses(void) {
    for (NSUInteger i = 0; i < 2; i++) {
        NGWCSlot *slot = &NGWCSlots[i];
        Class cls = objc_getClass(slot->name);
        if (!cls || !class_getInstanceMethod(cls, sel_registerName("tabBarItemViewAtIndex:"))) continue;
        slot->cls = cls;
        // Install input forwarding before layout can claim and mask a native bar.
        if (!NGWCInstall(cls, @selector(hitTest:withEvent:), (IMP)NGWCHit, &slot->hit, 4, '@', NULL)) continue;
        NGWCInstall(cls, @selector(didMoveToWindow), (IMP)NGWCWindow, &slot->window, 2, 'v', NULL);
        NGWCInstall(cls, sel_registerName(i ? "setSelectedIndex:" : "selectIndex:"), (IMP)NGWCSelected, &slot->selected, 3, 'v', "qQ");
        NGWCInstall(cls, @selector(setHidden:), (IMP)NGWCHidden, &slot->hidden, 3, 'v', "Bc");
        NGWCInstall(cls, @selector(setAlpha:), (IMP)NGWCAlpha, &slot->alpha, 3, 'v', "d");
        NGWCInstall(cls, @selector(layoutSubviews), (IMP)NGWCLayout, &slot->layout, 2, 'v', NULL);
    }
}

void NGInstallWeChatTabs(void) {
    if (!NSThread.isMainThread || !NGIsWeChatProcess()) return;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        NGWCInstallClasses();
        // Optional late-loaded classes; each IMP slot is installed once only.
        for (NSUInteger i = 1; i <= 3; i++) {
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)i * NSEC_PER_SEC), dispatch_get_main_queue(), ^{ NGWCInstallClasses(); });
        }
    });
}

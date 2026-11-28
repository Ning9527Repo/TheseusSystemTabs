#import "Host.h"
#import <objc/runtime.h>
#import <dispatch/dispatch.h>
#import <dlfcn.h>
#import <math.h>
#import <objc/message.h>

// The implementation lives in Swift; this narrow ObjC interface avoids importing a
// generated Swift header into the bridging header's own module.
@interface NGSystemTabsBridge : NSObject
+ (void)update:(UITabBar *)bar;
+ (void)detach:(UITabBar *)bar;
+ (void)suspend:(UITabBar *)bar;
+ (BOOL)usesOverlay:(UITabBar *)bar;
@end

typedef UIView *(*NGHitIMP)(UITabBar *, SEL, CGPoint, UIEvent *);
static NGHitIMP NGOrigHit;

static UIView *NGHit(UITabBar *bar, SEL cmd, CGPoint pt, UIEvent *event) {
    if (NSThread.isMainThread && [bar isKindOfClass:UITabBar.class] &&
        [NGSystemTabsBridge usesOverlay:bar]) return nil;
    return NGOrigHit(bar, cmd, pt, event);
}

static BOOL NGInstallHit(Class cls) {
    SEL sel = @selector(hitTest:withEvent:);
    Method method = class_getInstanceMethod(cls, sel);
    if (!method || method_getNumberOfArguments(method) != 4) return NO;
    char ret[8] = {0}, point[64] = {0}, event[8] = {0};
    method_getReturnType(method, ret, sizeof(ret));
    method_getArgumentType(method, 2, point, sizeof(point));
    method_getArgumentType(method, 3, event, sizeof(event));
    if (ret[0] != '@' || strcmp(point, @encode(CGPoint)) || event[0] != '@') return NO;
    NGHitIMP orig = (NGHitIMP)method_getImplementation(method);
    if (!orig || orig == NGHit) return NGOrigHit != NULL;
    NGOrigHit = orig;
    if (!class_addMethod(cls, sel, (IMP)NGHit, method_getTypeEncoding(method))) {
        NGOrigHit = (NGHitIMP)method_setImplementation(method, (IMP)NGHit);
    }
    return YES;
}

static NSUInteger NGTabCaptureDepth;
void NGSystemTabCaptureBegin(void) { NGTabCaptureDepth++; }
void NGSystemTabCaptureEnd(void) { if (NGTabCaptureDepth) NGTabCaptureDepth--; }
BOOL NGSystemTabIsCapturing(void) { return NGTabCaptureDepth != 0; }

static const UIControlEvents kNGPrimary = UIControlEventPrimaryActionTriggered;
static UIControlEvents NGActivationEvent(UIControl *control) {
    UIControlEvents events = control.allControlEvents;
    if (events & kNGPrimary) return kNGPrimary;
    if (events & UIControlEventTouchUpInside) return UIControlEventTouchUpInside;
    return 0;
}

void NGSystemTabNote(NSString *reason, UITabBar *bar) {
    static NSMutableDictionary<NSString *, NSNumber *> *counts;
    if (!NSThread.isMainThread) return;
    if (!counts) counts = [NSMutableDictionary dictionary];
    NSString *key = [NSString stringWithFormat:@"%@/%@", reason, bar ? NSStringFromClass(object_getClass(bar)) : @"process"];
    NSInteger count = [counts[key] integerValue];
    if (count >= 8) return;
    counts[key] = @(count + 1);
    NSString *line = [NSString stringWithFormat:@"%@ %@ bars=%lu selected=%@ view=%.0fx%.0f\n", [NSDate date], key, (unsigned long)bar.items.count, bar.selectedItem ? @"yes" : @"no", bar.bounds.size.width, bar.bounds.size.height];
    NSString *path = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Caches/TheseusSystemTabs.log"];
    NSFileManager *fm = NSFileManager.defaultManager;
    [fm createDirectoryAtPath:path.stringByDeletingLastPathComponent withIntermediateDirectories:YES attributes:nil error:nil];
    if (![fm fileExistsAtPath:path]) [fm createFileAtPath:path contents:nil attributes:nil];
    NSFileHandle *fd = [NSFileHandle fileHandleForWritingAtPath:path];
    @try { [fd seekToEndOfFile]; [fd writeData:[line dataUsingEncoding:NSUTF8StringEncoding]]; } @catch (NSException *e) { (void)e; }
    [fd closeFile];
}

NSArray<UIControl *> *NGSystemTabControls(UITabBar *bar, NSInteger expectedCount) {
    if (expectedCount < 2 || expectedCount > 5 || !bar.window) return nil;
    NSUInteger count = (NSUInteger)expectedCount;
    Class button = NSClassFromString(@"UITabBarButton");
    if (!button) return nil;
    NSMutableArray<UIControl *> *controls = [NSMutableArray arrayWithCapacity:count];
    NSMutableArray<UIView *> *queue = [bar.subviews mutableCopy];
    for (NSUInteger index = 0; index < queue.count && index < 128; index++) {
        UIView *view = queue[index];
        if (view.hidden) continue;
        if ([view isKindOfClass:button] && [view isKindOfClass:UIControl.class]) {
            if (CGRectIsEmpty(view.bounds)) return nil;
            [controls addObject:(UIControl *)view];
        } else {
            [queue addObjectsFromArray:view.subviews];
        }
        if (queue.count > 128 || controls.count > count) return nil;
    }
    if (controls.count != count) return nil;
    [controls sortUsingComparator:^NSComparisonResult(UIControl *a, UIControl *b) {
        CGFloat x = [a convertPoint:CGPointMake(CGRectGetMidX(a.bounds), CGRectGetMidY(a.bounds)) toView:bar].x;
        CGFloat y = [b convertPoint:CGPointMake(CGRectGetMidX(b.bounds), CGRectGetMidY(b.bounds)) toView:bar].x;
        return x < y ? NSOrderedAscending : (x > y ? NSOrderedDescending : NSOrderedSame);
    }];
    if (bar.effectiveUserInterfaceLayoutDirection == UIUserInterfaceLayoutDirectionRightToLeft) {
        controls = [[controls.reverseObjectEnumerator allObjects] mutableCopy];
    }
    CGFloat last = NAN;
    for (UIControl *control in controls) {
        CGRect frame = [control convertRect:control.bounds toView:bar];
        CGFloat center = CGRectGetMidX(frame);
        if (!isfinite(center) || frame.size.width < 20 || !CGRectContainsPoint(bar.bounds, CGPointMake(center, CGRectGetMidY(frame))) || (isfinite(last) && fabs(last-center) < 15)) return nil;
        last = center;
    }
    return controls;
}

NSString *NGSystemTabButtonTitle(UIControl *control, NSString *badgeValue) {
    // Do not use badge text or a full accessibility utterance as a visible title.
    NSMutableArray<UIView *> *queue = [control.subviews mutableCopy];
    NSString *title = nil;
    for (NSUInteger i = 0; i < queue.count && i < 32; ++i) {
        UIView *view = queue[i];
        NSString *name = NSStringFromClass(object_getClass(view));
        if ([name rangeOfString:@"badge" options:NSCaseInsensitiveSearch].location != NSNotFound) continue;
        if ([view isKindOfClass:UILabel.class]) {
            UILabel *label = (UILabel *)view;
            NSString *text = [label.text stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
            if (text.length > 0 && ![text isEqualToString:badgeValue] && (!view.hidden || title == nil)) {
                if (!view.hidden) return text;
                title = text;
            }
        }
        if (queue.count + view.subviews.count <= 32) [queue addObjectsFromArray:view.subviews];
    }
    return title;
}

UIImage *NGSystemTabButtonImage(UIControl *control) {
    NSMutableArray<UIView *> *queue = [control.subviews mutableCopy];
    UIImage *hiddenImage = nil;
    for (NSUInteger i = 0; i < queue.count && i < 32; ++i) {
        UIView *view = queue[i];
        NSString *name = NSStringFromClass(object_getClass(view));
        if ([name rangeOfString:@"badge" options:NSCaseInsensitiveSearch].location != NSNotFound ||
            [name rangeOfString:@"background" options:NSCaseInsensitiveSearch].location != NSNotFound) continue;
        if ([view isKindOfClass:UIImageView.class]) {
            UIImageView *imageView = (UIImageView *)view;
            UIImage *image = imageView.image;
            if (image && image.size.width > 0 && image.size.height > 0 &&
                image.size.width <= 96 && image.size.height <= 96) {
                if (!view.hidden && view.alpha > 0.01) return image;
                if (!hiddenImage) hiddenImage = image;
            }
        }
        if (queue.count + view.subviews.count <= 32) [queue addObjectsFromArray:view.subviews];
    }
    return hiddenImage;
}

BOOL NGActivateSystemTabControl(UITabBar *bar, UIControl *control) {
    if (!bar || !control || !control.enabled || !control.window || !bar.window) return NO;
    // UIKit handles selection before dispatching its private control event.
    SEL buttonUp = NSSelectorFromString(@"_buttonUp:");
    Method method = class_getInstanceMethod(object_getClass(bar), buttonUp);
    if (method && method_getNumberOfArguments(method) == 3) {
        char ret[8] = {0}, arg[8] = {0};
        method_getReturnType(method, ret, sizeof(ret));
        method_getArgumentType(method, 2, arg, sizeof(arg));
        if (ret[0] == 'v' && arg[0] == '@') {
            ((void (*)(id, SEL, id))objc_msgSend)(bar, buttonUp, control);
            return YES;
        }
    }
    UIControlEvents event = NGActivationEvent(control);
    if (!event) { NGSystemTabNote(@"no-button-action", bar); return NO; }
    [control sendActionsForControlEvents:event];
    return YES;
}

NSString *NGTabResourceBundlePath(void) {
    Dl_info info = {0};
    if (!dladdr((const void *)&NGTabResourceBundlePath, &info) || !info.dli_fname) return nil;
    NSString *file = [NSFileManager.defaultManager stringWithFileSystemRepresentation:info.dli_fname length:strlen(info.dli_fname)];
    return [file.stringByDeletingLastPathComponent stringByAppendingPathComponent:@"TheseusSystemTabsResources.bundle"];
}

static BOOL NGIsBaseBar(UITabBar *bar) {
    return NSThread.isMainThread && [bar isKindOfClass:UITabBar.class];
}

static void (*NGOrigLayout)(UITabBar *, SEL);
static void (*NGOrigWindow)(UITabBar *, SEL);
static void (*NGOrigSelected)(UITabBar *, SEL, UITabBarItem *);

static void NGLayout(UITabBar *bar, SEL cmd) {
    NGOrigLayout(bar, cmd);
    if (NGIsBaseBar(bar) && !NGSystemTabIsCapturing()) {
        NGSystemTabNote(@"layout", bar);
        [NGSystemTabsBridge update:bar];
    }
}

static void NGWindow(UITabBar *bar, SEL cmd) {
    NGOrigWindow(bar, cmd);
    if (NGIsBaseBar(bar)) {
        if (!bar.window) [NGSystemTabsBridge suspend:bar];
        else [NGSystemTabsBridge update:bar];
    }
}

static void NGSelected(UITabBar *bar, SEL cmd, UITabBarItem *item) {
    NGOrigSelected(bar, cmd, item);
    if (NGIsBaseBar(bar) && bar.window) [bar setNeedsLayout];
}

static void NGInstall(Class cls, SEL sel, IMP replacement, IMP *original, unsigned nargs) {
    Method method = class_getInstanceMethod(cls, sel);
    if (*original || !method || method_getNumberOfArguments(method) != nargs) return;
    char ret[8] = {0};
    method_getReturnType(method, ret, sizeof(ret));
    if (ret[0] != 'v') return;
    if (nargs == 3) {
        char arg[16] = {0};
        method_getArgumentType(method, 2, arg, sizeof(arg));
        if (arg[0] != '@') return;
    }
    IMP impl = method_getImplementation(method);
    if (!impl || impl == replacement) return;
    *original = impl;
    // Do not alter an inherited implementation on UIView.
    if (!class_addMethod(cls, sel, replacement, method_getTypeEncoding(method))) {
        *original = method_setImplementation(method, replacement);
    }
}

static void NGInstallAll(void) {
    NGSystemTabNote(@"loaded-own-replacement", nil);
    Class cls = UITabBar.class;
    if (!NGInstallHit(cls)) { NGSystemTabNote(@"hit-hook-rejected", nil); return; }
    NGInstall(cls, @selector(layoutSubviews), (IMP)NGLayout, (IMP *)&NGOrigLayout, 2);
    NGInstall(cls, @selector(didMoveToWindow), (IMP)NGWindow, (IMP *)&NGOrigWindow, 2);
    NGInstall(cls, @selector(setSelectedItem:), (IMP)NGSelected, (IMP *)&NGOrigSelected, 3);
    NGSystemTabNote(NGOrigLayout ? @"own-replacement-hooks-installed" : @"layout-hook-rejected", nil);
}

__attribute__((constructor)) static void NGStart(void) {
    NSBundle *main = NSBundle.mainBundle;
    NSString *identifier = main.bundleIdentifier;
    if (NGIsWeChatProcess()) {
        if (NSThread.isMainThread) NGInstallWeChatTabs();
        else dispatch_async(dispatch_get_main_queue(), ^{ NGInstallWeChatTabs(); });
        return;
    }
    if (![main.bundlePath.pathExtension isEqualToString:@"app"] || !identifier.length ||
        [identifier hasPrefix:@"com.tencent.xin"] || [identifier isEqualToString:@"com.apple.springboard"]) return;
    if (NSThread.isMainThread) NGInstallAll();
    else dispatch_async(dispatch_get_main_queue(), ^{ NGInstallAll(); });
}

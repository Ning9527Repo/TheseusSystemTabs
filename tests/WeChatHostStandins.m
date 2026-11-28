#import "WeChatUIKitStub.h"
#import <objc/runtime.h>
#import <objc/message.h>
#import <dispatch/dispatch.h>
#import <stdio.h>
#import <stdlib.h>
#import <string.h>

@implementation UIResponder
@end
@implementation UIView
- (instancetype)init { if ((self = [super init])) { _bounds = CGRectMake(0, 0, 390, 83); _alpha = 1; _subviews = [NSMutableArray array]; } return self; }
- (void)layoutSubviews {}
- (void)didMoveToWindow {}
- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event { (void)point; (void)event; return self; }
@end
@implementation UIWindow
@end
@implementation UIControl
- (instancetype)init { if ((self = [super init])) _enabled = YES; return self; }
@end
@implementation UIEvent
@end
@implementation UIImage
- (instancetype)init { if ((self = [super init])) _size = CGSizeMake(24, 24); return self; }
@end
@implementation UIColor
@end
@implementation UIImageView
@end
@implementation UILabel
@end
@implementation UITabBar
@end
@implementation UIViewController
@end
@implementation UITabBarController
- (void)setSelectedIndex:(NSUInteger)index { _selectedIndex = index; self.selectedViewController = self.viewControllers[index]; self.tabBar.selectedItem = self.tabBar.items[index]; }
@end

@interface WCTabBarItem : NSObject
@property(nonatomic, copy) NSString *title;
@property(nonatomic, strong) UIImage *image;
@property(nonatomic, strong) UIImage *selectedImage;
@property(nonatomic, strong) UIColor *titleColor;
@property(nonatomic, strong) UIColor *selectedTitleColor;
@property(nonatomic, copy) NSString *badgeValue;
@property(nonatomic, getter=isEnabled) BOOL enabled;
@property(nonatomic) BOOL showsRedDot;
@property(nonatomic, copy) NSString *accessibilityLabel;
@end
@implementation WCTabBarItem
- (instancetype)init { if ((self = [super init])) { _title = @"WeChat"; _image = [UIImage new]; _selectedImage = [UIImage new]; _enabled = YES; } return self; }
@end
@interface WCTabBarItemView : UIControl
@property(nonatomic, strong) WCTabBarItem *item;
@end
@implementation WCTabBarItemView
@end
@interface WCTabBarView : UIView
@property(nonatomic, copy) NSArray<WCTabBarItem *> *tabItems;
@property(nonatomic, copy) NSArray<WCTabBarItemView *> *itemViews;
@property(nonatomic) NSUInteger selectedIndex;
@property(nonatomic, copy) void (^itemSelectionHandler)(NSUInteger);
@property(nonatomic) NSUInteger calls;
- (UIView *)tabBarItemViewAtIndex:(NSInteger)index;
- (void)onItemViewTouchUpInside:(UIControl *)item;
@end
@implementation WCTabBarView
- (UIView *)tabBarItemViewAtIndex:(NSInteger)index { return self.itemViews[(NSUInteger)index]; }
- (void)onItemViewTouchUpInside:(UIControl *)item {
    if (!item.enabled || item.tag < 0 || (NSUInteger)item.tag >= self.tabItems.count || !self.itemSelectionHandler) return;
    self.calls += 1; self.itemSelectionHandler((NSUInteger)item.tag);
}
@end
@interface NewMainTabBarViewController : UIViewController
@property(nonatomic, strong) WCTabBarView *tabBarView;
@end
@implementation NewMainTabBarViewController
@end

@interface MMTabbarItem : WCTabBarItem
@end
@implementation MMTabbarItem
@end
@interface MMTabBarItemView : UIView
@property(nonatomic, strong) MMTabbarItem *item;
@property(nonatomic) NSInteger unreadCount;
@property(nonatomic, copy) NSString *badgeString;
@property(nonatomic, strong) UIView *badgeView;
@end
@implementation MMTabBarItemView
@end
@interface MMTabBar : UITabBar
@property(nonatomic, copy) NSArray<MMTabBarItemView *> *itemViews;
- (UIView *)tabBarItemViewAtIndex:(NSInteger)index;
- (void)selectIndex:(NSInteger)index;
@end
@implementation MMTabBar
- (UIView *)tabBarItemViewAtIndex:(NSInteger)index { return self.itemViews[(NSUInteger)index]; }
- (void)selectIndex:(NSInteger)index { self.selectedItem = self.items[(NSUInteger)index]; }
@end
@interface MainTabBarViewController : UITabBarController <UITabBarControllerDelegate>
@property(nonatomic) BOOL allow;
@property(nonatomic) NSUInteger didSelectCount;
@end
@implementation MainTabBarViewController
- (BOOL)tabBarController:(UITabBarController *)bar shouldSelectViewController:(UIViewController *)controller { (void)bar; (void)controller; return self.allow; }
- (void)tabBarController:(UITabBarController *)bar didSelectViewController:(UIViewController *)controller { (void)bar; (void)controller; self.didSelectCount += 1; }
@end

static BOOL ngTestCapturing;
void NGSystemTabCaptureBegin(void) { ngTestCapturing = YES; }
void NGSystemTabCaptureEnd(void) { ngTestCapturing = NO; }
BOOL NGSystemTabIsCapturing(void) { return ngTestCapturing; }
BOOL NGIsWeChatProcess(void);
// BODY_INSERTED_HERE

static BOOL ngTestOverlay;
@implementation NGWeChatTabsBridge
+ (void)update:(UIView *)bar { (void)bar; }
+ (void)detach:(UIView *)bar { (void)bar; }
+ (BOOL)usesOverlay:(UIView *)bar { (void)bar; return ngTestOverlay; }
@end

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "failed line %d: %s\n", __LINE__, #x); abort(); } } while (0)
int main(void) { @autoreleasepool {
    UIWindow *window = [UIWindow new];
    NewMainTabBarViewController *owner = [NewMainTabBarViewController new];
    WCTabBarView *bar = [WCTabBarView new]; bar.window = window; bar.nextResponder = owner; owner.tabBarView = bar;
    NSMutableArray *items = [NSMutableArray array], *views = [NSMutableArray array];
    for (NSInteger i=0;i<4;i++) { WCTabBarItem *m=[WCTabBarItem new]; m.title=[NSString stringWithFormat:@"Tab%ld",(long)i]; WCTabBarItemView *v=[WCTabBarItemView new]; v.item=m;v.tag=i;[items addObject:m];[views addObject:v]; }
    bar.tabItems=items;bar.itemViews=views;
    __weak WCTabBarView *weakBar=bar;
    bar.itemSelectionHandler=^(NSUInteger i){ weakBar.selectedIndex=i; };
    CHECK(NGWeChatCopyTabs(bar).entries.count==4);
    for (NSInteger i=0;i<4;i++) CHECK(NGWeChatActivateTab(bar,i)==i);
    CHECK(bar.calls==4);
    bar.itemSelectionHandler=^(NSUInteger i){(void)i;};
    CHECK(NGWeChatActivateTab(bar,1)==3); // native callback may reject selection
    ((WCTabBarItem *)items[1]).enabled=NO;CHECK(NGWeChatActivateTab(bar,1)==-1);
    CHECK(NGWeChatActivateTab(bar,-1)==-1 && NGWeChatActivateTab(bar,4)==-1);
    ((WCTabBarItemView *)views[0]).tag=9;CHECK(NGWeChatCopyTabs(bar)==nil);((WCTabBarItemView *)views[0]).tag=0;
    ((WCTabBarItem *)items[0]).badgeValue=@"12"; ((WCTabBarItem *)items[2]).showsRedDot=YES;
    NGWeChatTabSnapshot *snap=NGWeChatCopyTabs(bar);CHECK([snap.entries[0].badge isEqualToString:@"12"] && snap.entries[2].redDot);
    UIViewController *otherOwner=[UIViewController new];bar.nextResponder=otherOwner;CHECK(NGWeChatCopyTabs(bar)==nil);bar.nextResponder=owner;
    bar.window=nil;CHECK(NGWeChatCopyTabs(bar)==nil);bar.window=window;
    NSArray *four=bar.tabItems;bar.tabItems=@[items[0]];CHECK(NGWeChatCopyTabs(bar)==nil);bar.tabItems=four;
    MainTabBarViewController *legacyOwner=[MainTabBarViewController new];MMTabBar *legacy=[MMTabBar new];legacy.window=window;legacy.nextResponder=legacyOwner;legacyOwner.tabBar=legacy;legacyOwner.delegate=legacyOwner;legacyOwner.allow=YES;
    NSMutableArray *legacyModels=[NSMutableArray array],*legacyViews=[NSMutableArray array],*controllers=[NSMutableArray array];
    for (NSInteger i=0;i<4;i++) {MMTabbarItem *m=[MMTabbarItem new];MMTabBarItemView *v=[MMTabBarItemView new];v.item=m;[legacyModels addObject:m];[legacyViews addObject:v];[controllers addObject:[UIViewController new]];}
    legacy.items=legacyModels;legacy.itemViews=legacyViews;legacyOwner.viewControllers=controllers;legacyOwner.selectedIndex=0;
    CHECK(NGWeChatCopyTabs(legacy).selectedIndex==0);CHECK(NGWeChatActivateTab(legacy,2)==2 && legacyOwner.didSelectCount==1);
    legacyOwner.allow=NO;CHECK(NGWeChatActivateTab(legacy,0)==2 && legacyOwner.didSelectCount==1);
    ((MMTabBarItemView *)legacyViews[0]).unreadCount=128;CHECK([NGWeChatCopyTabs(legacy).entries[0].badge isEqualToString:@"99+"]);
    NGWCInstallClasses();IMP first=NGWCSlots[1].layout;NGWCInstallClasses();CHECK(first==NGWCSlots[1].layout && first!=(IMP)NGWCLayout);
    ngTestOverlay=YES;CHECK([bar hitTest:CGPointZero withEvent:nil]==nil);bar.hidden=NO;NGSystemTabCaptureBegin();bar.hidden=YES;CHECK(!bar.hidden);NGSystemTabCaptureEnd();bar.hidden=YES;CHECK(bar.hidden);
    puts("wechat_production_snapshot_activation_hooks_ok");
}return 0;}

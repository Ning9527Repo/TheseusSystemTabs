#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>

@class UIView, UIWindow, UITabBar, UITabBarController, UIViewController, UIEvent;
@protocol UITabBarControllerDelegate <NSObject>
@optional
- (BOOL)tabBarController:(UITabBarController *)bar shouldSelectViewController:(UIViewController *)controller;
- (void)tabBarController:(UITabBarController *)bar didSelectViewController:(UIViewController *)controller;
@end
@interface UIResponder : NSObject
@property(nonatomic, weak) UIResponder *nextResponder;
@end
@interface UIView : UIResponder
@property(nonatomic) CGRect bounds;
@property(nonatomic, getter=isHidden) BOOL hidden;
@property(nonatomic) CGFloat alpha;
@property(nonatomic, weak) UIWindow *window;
@property(nonatomic, strong) NSMutableArray<UIView *> *subviews;
@property(nonatomic, copy) NSString *accessibilityLabel;
- (void)layoutSubviews;
- (void)didMoveToWindow;
- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event;
@end
@interface UIWindow : UIView
@end
@interface UIControl : UIView
@property(nonatomic, getter=isEnabled) BOOL enabled;
@property(nonatomic) NSInteger tag;
@end
@interface UIEvent : NSObject
@end
@interface UIImage : NSObject
@property(nonatomic) CGSize size;
@end
@interface UIColor : NSObject
@end
@interface UIImageView : UIView
@property(nonatomic, strong) UIImage *image;
@end
@interface UILabel : UIView
@property(nonatomic, copy) NSString *text;
@end
@interface UITabBar : UIView
@property(nonatomic, strong) NSArray *items;
@property(nonatomic, strong) id selectedItem;
@end
@interface UIViewController : UIResponder
@end
@interface UITabBarController : UIViewController
@property(nonatomic, strong) UITabBar *tabBar;
@property(nonatomic, copy) NSArray<UIViewController *> *viewControllers;
@property(nonatomic, weak) id<UITabBarControllerDelegate> delegate;
@property(nonatomic) NSUInteger selectedIndex;
@property(nonatomic, strong) UIViewController *selectedViewController;
@end

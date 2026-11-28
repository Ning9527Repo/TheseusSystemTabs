#import <UIKit/UIKit.h>
#import "WeChatHost.h"

NS_ASSUME_NONNULL_BEGIN
NSArray<UIControl *> * _Nullable NGSystemTabControls(UITabBar *bar, NSInteger expectedCount);
NSString * _Nullable NGSystemTabButtonTitle(UIControl *control, NSString * _Nullable badgeValue);
UIImage * _Nullable NGSystemTabButtonImage(UIControl *control);
BOOL NGActivateSystemTabControl(UITabBar *bar, UIControl *control);
void NGSystemTabCaptureBegin(void);
void NGSystemTabCaptureEnd(void);
BOOL NGSystemTabIsCapturing(void);
void NGSystemTabNote(NSString *reason, UITabBar * _Nullable bar);
NSString * _Nullable NGTabResourceBundlePath(void);
NS_ASSUME_NONNULL_END

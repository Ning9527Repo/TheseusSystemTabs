#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN
@interface NGWeChatTabEntry : NSObject
@property(nonatomic, strong) id identity;
@property(nonatomic, copy, nullable) NSString *title;
@property(nonatomic, strong, nullable) UIImage *image;
@property(nonatomic, strong, nullable) UIImage *selectedImage;
@property(nonatomic, copy, nullable) NSString *badge;
@property(nonatomic, strong, nullable) UIColor *selectedColor;
@property(nonatomic, strong, nullable) UIColor *normalColor;
@property(nonatomic, copy, nullable) NSString *label;
@property(nonatomic) BOOL enabled;
@property(nonatomic) BOOL redDot;
@end

@interface NGWeChatTabSnapshot : NSObject
@property(nonatomic, copy) NSArray<NGWeChatTabEntry *> *entries;
@property(nonatomic) NSInteger selectedIndex;
@end

BOOL NGIsWeChatProcess(void);
void NGInstallWeChatTabs(void);
NGWeChatTabSnapshot * _Nullable NGWeChatCopyTabs(UIView *bar);
NSInteger NGWeChatActivateTab(UIView *bar, NSInteger index);
NS_ASSUME_NONNULL_END

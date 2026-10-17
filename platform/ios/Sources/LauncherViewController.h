#import <UIKit/UIKit.h>

// Settings are committed before the first Metal device or guest preload exists.
@interface LauncherViewController : UIViewController
@property (copy) void (^onPlay)(BOOL wide, BOOL hud, BOOL metalfx);
- (instancetype)initWithWideAvailable:(BOOL)wide ready:(BOOL)ready reason:(NSString *)reason;
@end

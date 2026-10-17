// Bayonetta 3 iOS 壳的入口：开日志、找游戏资源（RomFS）、设宿主要读的环境变量、提前起跑宿主装载，场景到前台后在大栈线程上进 dm_main。
// 与暗黑外壳（../../Sources/main.m）相比只保留通用部分：没有模式探针、资源下载、覆盖层、iCloud、测试存档、日志端口。
// 资源：玩家用「文件」App 把 Update/RomFS 的内容（含 core_000.pkz）拷进本 App 的 Documents（文件夹名随意，外面多套几层也认，4 层以内）；
// 开发时也可以推到容器的 Library/Application Support/romfs：
//   xcrun devicectl device copy to --device <设备> --domain-type appDataContainer --domain-identifier <包名> --source <Update/RomFS> --destination 'Library/Application Support/romfs'
// Entry of the Bayonetta 3 iOS shell: open the log, locate the game assets (RomFS), set the environment variables the host reads, start host loading early,
// and enter dm_main on a large-stack thread once the scene is in the foreground.
// Compared with the Diablo shell (../../Sources/main.m) only the generic part is kept: no mode probes, asset download, overlay, iCloud, test saves or log port.
// Assets: the player copies the contents of Update/RomFS (containing core_000.pkz) into this App's Documents with the Files app (any folder name, up to 4 extra levels);
// during development it can also be pushed into the container's Library/Application Support/romfs (devicectl command above).
#import <UIKit/UIKit.h>
#import <Metal/Metal.h>
#import <MetalFX/MetalFX.h>
#include <os/proc.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
#include "front.h"
#import "LauncherViewController.h"

int dm_main(int argc, char **argv);                 // dm/host/main.c 以 -Dmain=dm_main 编入 | dm/host/main.c is compiled in with -Dmain=dm_main
void dm_host_shutdown(const char *why);             // dm/host/hle_lifecycle.c
UIView *front_blade_view(CGRect bounds, CGFloat scale);   // front_blade.m：Metal 出图视图 + 虚拟手柄（scale = 屏幕原生像素比） | front_blade.m: Metal present view + virtual gamepad (scale = native pixel ratio of the screen)
void front_blade_focus(int ev);                     // front_blade.m：场景生命周期 → 宿主 | front_blade.m: scene lifecycle → host

static int g_argc; static char *g_argv[8];
static NSString *g_romfs, *g_why;                   // 找到的资源目录 / 没找到的原因 | located asset dir / reason when not found
static _Atomic int g_host_started;
static BOOL g_launch_selected;

static NSDictionary *mobile_graphics(void) {
    NSData *data=[NSData dataWithContentsOfFile:[NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:@"dm/mobile-graphics.json"]];
    return data?[NSJSONSerialization JSONObjectWithData:data options:0 error:nil]:nil;
}

static void device_report(NSString *doc) {
    id<MTLDevice> gpu=MTLCreateSystemDefaultDevice();
    BOOL spatial=gpu && [MTLFXSpatialScalerDescriptor supportsDevice:gpu];
    NSDictionary *report=@{@"os":UIDevice.currentDevice.systemVersion,
        @"gpu":gpu.name?:@"unavailable", @"physical_memory":@(NSProcessInfo.processInfo.physicalMemory),
        @"available_memory":@(os_proc_available_memory()), @"recommended_gpu_working_set":@(gpu.recommendedMaxWorkingSetSize),
        @"bc_textures":@(gpu.supportsBCTextureCompression), @"metalfx_spatial":@(spatial),
        @"render_policy":[NSString stringWithUTF8String:getenv("DM_IOS_GRAPHICS_MODE")?:"normal"], @"output_policy":@"native-drawable-aspect-fit",
        @"metalfx_requested":@(!strcmp(getenv("DM_METALFX")?:"off","spatial")),
        @"metal_hud_requested":@(!strcmp(getenv("MTL_HUD_ENABLED")?:"0","1")),
        @"frame_generation":@NO};
    NSData *data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil];
    [data writeToFile:[doc stringByAppendingPathComponent:@"device-report.json"] atomically:YES];
    fprintf(stderr,"boot: iOS device report %s\n",[[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding].UTF8String);
}

static void plog(const char *fmt, ...) { va_list ap; va_start(ap, fmt); fprintf(stderr, "boot: "); vfprintf(stderr, fmt, ap); fputc('\n', stderr); va_end(ap); }

// 日志：Documents/boot.txt（「文件」App 里可见）；上一轮的留成 boot.previous.txt。宿主的 LOG / die 都写 stderr，重定向到同一文件
// Log: Documents/boot.txt (visible in the Files app); the previous run's is kept as boot.previous.txt. The host's LOG / die write to stderr, redirected to the same file
static void log_open(NSString *doc) {
    const char *cur = [doc stringByAppendingPathComponent:@"boot.txt"].fileSystemRepresentation, *prev = [doc stringByAppendingPathComponent:@"boot.previous.txt"].fileSystemRepresentation;
    rename(cur, prev);
    int fd = open(cur, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd >= 0) { dup2(fd, 2); close(fd); }
    setvbuf(stderr, NULL, _IOLBF, 0);
}

// RomFS 判据：目录下有 core_000.pkz（run_mac.sh 只核 Bayonetta3/，这里多核一层免得把空壳文件夹当资源）
// RomFS criterion: the directory contains core_000.pkz (run_mac.sh only checks Bayonetta3/; one more level here so an empty shell folder is not mistaken for assets)
static BOOL romfs_ok(NSString *dir) { BOOL d = NO; return [NSFileManager.defaultManager fileExistsAtPath:[dir stringByAppendingPathComponent:@"core_000.pkz"] isDirectory:&d] && !d; }
static NSString *romfs_search(NSString *dir, int depth) {
    if (romfs_ok(dir)) return dir;
    if (depth <= 0) return nil;
    for (NSString *n in [NSFileManager.defaultManager contentsOfDirectoryAtPath:dir error:nil]) {
        if ([n hasPrefix:@"."] || [n isEqualToString:@"save"] || [n isEqualToString:@"temp"]) continue;
        NSString *p = [dir stringByAppendingPathComponent:n]; BOOL d = NO;
        if ([NSFileManager.defaultManager fileExistsAtPath:p isDirectory:&d] && d) { NSString *r = romfs_search(p, depth - 1); if (r) return r; }
    }
    return nil;
}
static NSString *romfs_locate(NSString *doc) {
    NSString *lib = [NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, YES)[0] stringByAppendingPathComponent:@"romfs"];
    if (romfs_ok(lib)) return lib;
    NSString *r = romfs_search(doc, 4); if (r) return r;
    g_why = @"没找到游戏资源：请用「文件」App 把 Switch 版 Update/RomFS 的内容（含 core_000.pkz）拷进本 App 的文件夹，然后重新打开。\n"
             "Game assets not found: copy the contents of the Switch Update/RomFS (containing core_000.pkz) into this App's folder with the Files app, then reopen.";
    return nil;
}

// File names and lengths are generated into the private app, never published.
// Do not enter the guest while a Files/USB transfer is incomplete.
static BOOL assets_ready(NSString *doc, NSString *res) {
    NSData *data=[NSData dataWithContentsOfFile:[res stringByAppendingPathComponent:@"dm/private-assets.json"]];
    NSDictionary *inventory=data?[NSJSONSerialization JSONObjectWithData:data options:0 error:nil]:nil;
    if(![inventory[@"romfs"] count] || ![inventory[@"media"] count]) {
        g_why=@"资源清单缺失，请重新构建。\nPrivate resource inventory is missing; rebuild the app.";return NO;
    }
    for(NSString *kind in @[@"romfs",@"media"]) {
        NSString *root=[kind isEqual:@"romfs"]?g_romfs:[doc stringByAppendingPathComponent:@"media"];
        NSDictionary *files=inventory[kind];
        for(NSString *name in files) {
            NSDictionary *attributes=[NSFileManager.defaultManager attributesOfItemAtPath:[root stringByAppendingPathComponent:name] error:nil];
            if(![attributes[NSFileType] isEqual:NSFileTypeRegular] || [attributes[NSFileSize] unsignedLongLongValue]!=[files[name] unsignedLongLongValue]) {
                g_why=[NSString stringWithFormat:@"资源传输未完成：%@/%@\n请完成复制后重新打开。\nResource transfer incomplete: %@/%@. Reopen after copying finishes.",kind,name,kind,name];
                return NO;
            }
        }
    }
    plog("Resource inventory complete: %lu RomFS files / %lu AVC movies (file lengths checked; not a new content-hash proof)",(unsigned long)[inventory[@"romfs"] count],(unsigned long)[inventory[@"media"] count]);
    return YES;
}

// Prepare directories/resources only. Guest preload and Metal device creation
// wait until the user commits launch settings.
static void boot_prepare(NSString *doc) {
    NSFileManager *fm = NSFileManager.defaultManager; NSString *res = NSBundle.mainBundle.resourcePath;
    // Create transfer destinations even before assets arrive. devicectl's
    // individual-file service requires existing parent directories.
    for (NSString *d in @[@"save", @"temp", @"media"])
        [fm createDirectoryAtPath:[doc stringByAppendingPathComponent:d] withIntermediateDirectories:YES attributes:nil error:nil];
    NSString *support=NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory,NSUserDomainMask,YES)[0];
    NSString *transferRoot=[support stringByAppendingPathComponent:@"romfs"];
    [fm createDirectoryAtPath:transferRoot withIntermediateDirectories:YES attributes:nil error:nil];
    NSData *inventoryData=[NSData dataWithContentsOfFile:[res stringByAppendingPathComponent:@"dm/private-assets.json"]];
    NSDictionary *inventory=inventoryData?[NSJSONSerialization JSONObjectWithData:inventoryData options:0 error:nil]:nil;
    NSMutableSet *directories=[NSMutableSet set];
    for(NSString *name in inventory[@"romfs"]) {
        NSString *parent=name.stringByDeletingLastPathComponent;
        if(parent.length) [directories addObject:parent];
    }
    for(NSString *parent in directories)
        [fm createDirectoryAtPath:[transferRoot stringByAppendingPathComponent:parent] withIntermediateDirectories:YES attributes:nil error:nil];
    g_romfs = romfs_locate(doc);
    if (!g_romfs) { plog("%s", g_why.UTF8String); return; }
    if (!assets_ready(doc,res)) {g_romfs=nil;plog("%s",g_why.UTF8String);return;}
    setenv("DM_ROMFS", g_romfs.fileSystemRepresentation, 0);
    setenv("DM_SAVE", [doc stringByAppendingPathComponent:@"save"].fileSystemRepresentation, 0);
    setenv("DM_TEMP", [doc stringByAppendingPathComponent:@"temp"].fileSystemRepresentation, 0);
    setenv("DM_MOVIE_CACHE", [doc stringByAppendingPathComponent:@"media"].fileSystemRepresentation, 0);
    setenv("DM_MOVIE", "1", 0);setenv("DM_AUDIO", "1", 0);
    setenv("DM_MSL_DIR", [res stringByAppendingPathComponent:@"msl"].fileSystemRepresentation, 0);              // 宿主只从 DM_MSL_DIR/b-<V>/ 加载 | the host loads only from DM_MSL_DIR/b-<V>/
    setenv("DM_NVN_SHMAP", [res stringByAppendingPathComponent:@"dm/shader_map.tsv"].fileSystemRepresentation, 0);
    setenv("DM_NVN_TESS_DIR", [res stringByAppendingPathComponent:@"tessellation"].fileSystemRepresentation, 0);
    // Handheld SDK mode; the optional guarded profile synchronizes its targets.
    setenv("DM_OPMODE", "0", 0);
    setenv("DM_NVN_INDIRECT_BATCH", "1", 0);
    setenv("DM_METALFX", "spatial", 0);
    setenv("DM_FRAME_GENERATION", "off", 1);
    setenv("DM_NVN_TSV", [doc stringByAppendingPathComponent:@"frames.tsv"].fileSystemRepresentation, 0);
    setenv("DM_NVN_TSV_CALLS", "0", 0);
    setenv("DM_NVN_TSV_MAX_MB", "16", 0);
    // 与 Mac 上验证过的跑法一致（README 四 / 五）：预热清单关、TBDR 优化关（D2R 调的，Blade 未验证）、SysRes 0（Blade 的 npdm；通用宿主缺省已是 0）
    // Same as the run verified on Mac (README 四 / 五): warm-up manifest off, TBDR optimisations off (tuned for D2R, unverified on Blade), SysRes 0 (Blade's npdm; already the generic host default)
    setenv("DM_PSO_MANIFEST", "off", 0); setenv("DM_NVN_TBDR", "0", 0); setenv("DM_SYSRES_MB", "0", 0);
    setenv("DM_DBG", "1", 0);
    if (chdir(doc.fileSystemRepresentation)) plog("🔴 chdir Documents 失败 %s", strerror(errno));
    static char a0[] = "Bayonetta3", a2[] = "main", a3[] = "subsdk0", a4[] = "sdk";
    g_argv[0] = a0; g_argv[1] = strdup([res stringByAppendingPathComponent:@"dm"].fileSystemRepresentation); g_argv[2] = a2; g_argv[3] = a3; g_argv[4] = a4; g_argc = 5;   // App 内 dm/ = 产物目录（表头 / 门表；映像在可执行文件的段里） | dm/ inside the App = build output dir (table headers / gate tables; the images are in the executable's segments)
    plog("RomFS %s；产物目录 %s；着色器库 %s", g_romfs.UTF8String, g_argv[1], getenv("DM_MSL_DIR"));
}

static void *boot_thread(void *arg) { (void)arg; pthread_setname_np("dm-boot"); plog("dm_main"); int rc = dm_main(g_argc, g_argv); plog("dm_main 返回 %d", rc); return NULL; }
static void host_start(void) {
    if (!g_romfs || atomic_exchange(&g_host_started, 1)) return;
    pthread_attr_t a; pthread_attr_init(&a); pthread_attr_setstacksize(&a, 64 << 20);   // 客体主线程跑在这条线程上（SDK 自己再给线程换客体栈） | the guest main thread runs on this thread (the SDK switches threads to guest stacks itself)
    pthread_t t; pthread_create(&t, &a, boot_thread, NULL); pthread_detach(t);
}

@interface App : UIResponder <UIApplicationDelegate> @end
@implementation App @end

@interface GameVC : UIViewController @end
@implementation GameVC
- (BOOL)prefersStatusBarHidden { return YES; }
- (BOOL)prefersHomeIndicatorAutoHidden { return YES; }
- (UIRectEdge)preferredScreenEdgesDeferringSystemGestures { return UIRectEdgeAll; }   // 边缘手势延迟：摇杆贴边不会误拉出控制中心 | Defer edge gestures: a stick near the edge does not pull in Control Center
- (UIInterfaceOrientationMask)supportedInterfaceOrientations { return UIInterfaceOrientationMaskLandscape; }
@end

@interface SceneDelegate : UIResponder <UIWindowSceneDelegate>
@property (strong, nonatomic) UIWindow *window;
@end
@implementation SceneDelegate
- (void)startWide:(BOOL)wide hud:(BOOL)hud metalfx:(BOOL)metalfx {
    if(g_launch_selected||!g_romfs)return;
    NSDictionary *graphics=mobile_graphics();
    if(wide && (![graphics[@"startup_selection"] boolValue] || ![graphics[@"mode"] isEqual:@"mobile-expanded-fov"] ||
                [graphics[@"parameters"][@"width"] intValue]!=1568 || [graphics[@"parameters"][@"height"] intValue]!=720)) {
        UIAlertController *alert=[UIAlertController alertControllerWithTitle:@"Bayonetta 3" message:@"宽屏配置无效，请重新构建。\nInvalid wide profile; rebuild the app." preferredStyle:UIAlertControllerStyleAlert];
        [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
        [self.window.rootViewController presentViewController:alert animated:YES completion:nil];return;
    }
    // These settings take precedence over debugger launch variables. Set HUD
    // before even querying MTLCreateSystemDefaultDevice, and choose the signed
    // image before starting the loader's background thread.
    setenv("DM_IOS_GRAPHICS_MODE",wide?"wide":"normal",1);
    if(wide)setenv("DM_GAME_RES","1568x720",1);else unsetenv("DM_GAME_RES");
    setenv("MTL_HUD_ENABLED",hud?"1":"0",1);
    setenv("DM_METALFX",metalfx?"spatial":"off",1);
    plog("Launch settings: mode=%s Metal-HUD=%s MetalFX=%s signed-main=%s",wide?"wide":"normal",hud?"on":"off",metalfx?"spatial":"off",
         [graphics[wide?@"configured_sha256":@"normal_image_sha256"] UTF8String]?:"original");
    NSString *doc=NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,NSUserDomainMask,YES)[0];
    device_report(doc);
    if(!getenv("DM_NO_PRELOAD"))dm_host_preload_start(g_argc,g_argv);
    GameVC *vc=[GameVC new];UIWindowScene *ws=self.window.windowScene;
    vc.view=front_blade_view(ws.effectiveGeometry.coordinateSpace.bounds,ws.screen.nativeScale);
    vc.view.accessibilityIdentifier=@"game-canvas";
    self.window.rootViewController=vc;g_launch_selected=YES;
    dispatch_async(dispatch_get_main_queue(),^{if(UIApplication.sharedApplication.applicationState==UIApplicationStateActive)host_start();});
}
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)s options:(UISceneConnectionOptions *)o {
    UIWindowScene *ws = (UIWindowScene *)scene;
    self.window = [[UIWindow alloc] initWithWindowScene:ws];
    LauncherViewController *vc=[[LauncherViewController alloc] initWithWideAvailable:[mobile_graphics()[@"startup_selection"] boolValue] ready:g_romfs!=nil reason:g_why];
    __weak SceneDelegate *weakSelf=self;
    vc.onPlay=^(BOOL wide,BOOL hud,BOOL metalfx){[weakSelf startWide:wide hud:hud metalfx:metalfx];};
    self.window.rootViewController = vc; [self.window makeKeyAndVisible];
    // Keep the foreground transfer/instructions screen awake too.
    UIApplication.sharedApplication.idleTimerDisabled = YES;
}
- (void)sceneDidBecomeActive:(UIScene *)s { if (atomic_load(&g_host_started)) front_blade_focus(3); else if(g_launch_selected)host_start(); }
- (void)sceneWillResignActive:(UIScene *)s { if (atomic_load(&g_host_started)) front_blade_focus(0); }
- (void)sceneDidEnterBackground:(UIScene *)s { if (atomic_load(&g_host_started)) front_blade_focus(1); }
- (void)sceneWillEnterForeground:(UIScene *)s { if (atomic_load(&g_host_started)) front_blade_focus(2); }
- (void)sceneDidDisconnect:(UIScene *)s { if (atomic_load(&g_host_started)) dm_host_shutdown("iOS 场景断开"); }
@end

int main(int argc, char **argv) {
    { struct rlimit rl; if (!getrlimit(RLIMIT_NOFILE, &rl)) { rlim_t want = 4096; if (rl.rlim_max != RLIM_INFINITY && want > rl.rlim_max) want = rl.rlim_max; if (rl.rlim_cur < want) { rl.rlim_cur = want; setrlimit(RLIMIT_NOFILE, &rl); } } }   // pak + 过场视频同时开的文件数 | files open at once: paks + movies
    NSString *doc = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES)[0];
    log_open(doc);
    plog("Bayonetta 3 iOS 壳 %s（%s）", [NSBundle.mainBundle.infoDictionary[@"CFBundleShortVersionString"] description].UTF8String, UIDevice.currentDevice.systemVersion.UTF8String);
    boot_prepare(doc);
    @autoreleasepool { return UIApplicationMain(argc, argv, nil, NSStringFromClass(App.class)); }
}

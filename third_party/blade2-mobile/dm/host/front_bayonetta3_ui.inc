// Small native controls; all state and AppKit access stay on the main thread.
static NSTextField *g_bayo_hud;
static NSButton *g_bayo_hud_button;
static NSMenuItem *g_bayo_hud_menu,*g_bayo_fx_menu;
static BOOL g_bayo_fx_active=YES;
static BOOL g_bayo_hud_visible;
static NSString *bayo_text(NSString *zh,NSString *en){return [NSLocale.preferredLanguages.firstObject hasPrefix:@"zh"]?zh:en;}
static void bayo_hud_visible(BOOL visible){
    g_bayo_hud_visible=visible;g_bayo_hud.hidden=!visible;
    g_bayo_hud_button.state=visible?NSControlStateValueOn:NSControlStateValueOff;
    g_bayo_hud_menu.state=g_bayo_hud_button.state;
    [NSUserDefaults.standardUserDefaults setBool:visible forKey:@"BayonettaPerformanceHUD"];
    LOG("[window] performance HUD %s",visible?"on":"off");
}
static void bayo_window_controls(id controller){
    NSTitlebarAccessoryViewController *accessory=[NSTitlebarAccessoryViewController new];
    NSStackView *controls=[NSStackView new];controls.orientation=NSUserInterfaceLayoutOrientationHorizontal;controls.spacing=8;
    controls.edgeInsets=NSEdgeInsetsMake(3,4,3,8);
    g_bayo_hud_button=[NSButton buttonWithTitle:@"HUD" target:controller action:@selector(toggleHUD:)];
    [g_bayo_hud_button setButtonType:NSButtonTypePushOnPushOff];g_bayo_hud_button.bezelStyle=NSBezelStyleRounded;
    g_bayo_hud_button.toolTip=bayo_text(@"显示或隐藏性能数据（⌘⇧H）",@"Show or hide performance (⇧⌘H)");g_bayo_hud_button.accessibilityLabel=bayo_text(@"性能 HUD",@"Performance HUD");
    NSButton *full=[NSButton buttonWithTitle:bayo_text(@"全屏",@"Full Screen") target:controller action:@selector(fullscreen:)];
    full.bezelStyle=NSBezelStyleRounded;full.image=[NSImage imageWithSystemSymbolName:@"arrow.up.left.and.arrow.down.right" accessibilityDescription:nil];full.imagePosition=NSImageLeft;
    full.toolTip=bayo_text(@"切换全屏（⌃⌘F）",@"Toggle full screen (⌃⌘F)");
    [controls addArrangedSubview:g_bayo_hud_button];[controls addArrangedSubview:full];
    controls.frame=NSMakeRect(0,0,210,30);accessory.view=controls;accessory.layoutAttribute=NSLayoutAttributeRight;accessory.fullScreenMinHeight=30;
    [g_win addTitlebarAccessoryViewController:accessory];
    g_bayo_hud=[NSTextField wrappingLabelWithString:@""];
    g_bayo_hud.frame=NSMakeRect(g_view.bounds.size.width-338,g_view.bounds.size.height-112,320,94);
    g_bayo_hud.autoresizingMask=NSViewMinXMargin|NSViewMinYMargin;
    g_bayo_hud.font=[NSFont monospacedDigitSystemFontOfSize:12 weight:NSFontWeightMedium];g_bayo_hud.textColor=NSColor.whiteColor;
    g_bayo_hud.drawsBackground=YES;g_bayo_hud.backgroundColor=[NSColor colorWithWhite:.025 alpha:.88];
    g_bayo_hud.selectable=NO;g_bayo_hud.editable=NO;g_bayo_hud.bordered=NO;
    [g_view addSubview:g_bayo_hud];
    NSUserDefaults *defaults=NSUserDefaults.standardUserDefaults;
    bayo_hud_visible([defaults objectForKey:@"BayonettaPerformanceHUD"]?[defaults boolForKey:@"BayonettaPerformanceHUD"]:YES);
    [NSTimer scheduledTimerWithTimeInterval:.5 repeats:YES block:^(NSTimer *timer){
        (void)timer;void mtl_front_stats(uint64_t *,double *);void mtl_present_stats(uint64_t *,uint64_t *,int *);
        static uint64_t before,shown_before,generated_before;static double then;uint64_t frame,shown,generated;double gpu;int fx;
        mtl_front_stats(&frame,&gpu);mtl_present_stats(&shown,&generated,&fx);
        double now=CACurrentMediaTime(),dt=then>0?now-then:0,fps=dt>0?(frame-before)/dt:0,display=dt>0?(shown-shown_before)/dt:0,fg=dt>0?(generated-generated_before)/dt:0;
        before=frame;shown_before=shown;generated_before=generated;then=now;
        g_bayo_fx_active=fx;g_bayo_fx_menu.state=fx?NSControlStateValueOn:NSControlStateValueOff;
        NSString *gpuText=gpu>=0?[NSString stringWithFormat:@"%.2f ms",gpu]:@"—";
        g_bayo_hud.stringValue=[NSString stringWithFormat:@"  Game %.1f FPS   %.2f ms\n  Display %.1f FPS   Generated %.1f\n  Game GPU %@\n  %@",fps,fps>0?1000/fps:0,display,fg,gpuText,fx?@"1920×1080 → 3840×2160 · MetalFX":@"Native presentation"];
    }];
    const char *root=getenv("DM_SOURCE_ROOT");
    NSString *icon=root?[[@(root) stringByAppendingPathComponent:@"work/build/icons"] stringByAppendingPathComponent:@"AppIcon.png"]:nil;
    NSImage *image=icon?[[NSImage alloc]initWithContentsOfFile:icon]:nil;
    if(!image)image=[NSImage imageNamed:@"AppIcon"];
    if(image)NSApp.applicationIconImage=image;
}

"""Host-only presentation and interaction adapters; do not edit the vendor tree."""


def drag_tab(s, rep):
    s = rep(s, 'selectionAnimator?.follow(x: location.x + fingerAnchorOffset, at: time)',
            'selectionAnimator?.follow(x: location.x + fingerAnchorOffset, at: time, direct: ngUseHostPosition)')
    s = rep(s, '    private var flyWait: CFTimeInterval = SelectionAnimator.flyDelay',
            '    private var flyWait: CFTimeInterval = SelectionAnimator.flyDelay\n    private var ngDragCenter = NGTabDirectFollow()')
    s = rep(s, '    func follow(x: CGFloat, at time: CFTimeInterval) {\n', '''    func follow(x: CGFloat, at time: CFTimeInterval, direct: Bool = false) {
        guard x.isFinite else { return }
        if direct, ngDragCenter.update(x) {
            // During actual movement, the latest touch owns X. The grow and
            // release springs still own size and the landing animation.
            if displayLink != nil { cancel() }
            guard let frame = frameForCenterX?(x), frame != targetFrame || centerX != frame.midX else { return }
            targetFrame = frame
            centerX = frame.midX
            onFrameChanged?(frame)
            return
        }
''')
    s = rep(s, '        flyWait = immediate ? 0 : Self.flyDelay\n',
            '        flyWait = immediate ? 0 : Self.flyDelay\n        ngDragCenter.reset()\n')
    s = rep(s, '                    if self.ngUseHostPosition { self.ngFollowFrame = frame }\n                    else { morph.retarget(to: containerFrame) }', '''                    if self.ngUseHostPosition {
                        self.ngFollowFrame = frame
                        if let lens = self.theseusView {
                            // Update this display state now; the grow tick
                            // reads the same center rather than a spring lagging behind it.
                            let current = lens.layer.frame
                            var transform = lens.layer.transform
                            transform.m41 += containerFrame.midX - current.midX
                            transform.m42 += containerFrame.midY - current.midY
                            lens.layer.transform = transform
                        }
                    } else { morph.retarget(to: containerFrame) }''')
    s = rep(s, '        onFrameChanged?(currentFrame)\n    }\n\n    /// A lingering follow tick',
            '        onFrameChanged?(ngDragCenter.isTracking ? targetFrame : currentFrame)\n    }\n\n    /// A lingering follow tick')
    s = rep(s, '    private var captureTitleSource: (title: String, tint: UIColor, scale: CGFloat, size: CGSize)?',
            '''    private var captureTitleSource: (title: String, tint: UIColor, scale: CGFloat, size: CGSize)?
    private var ngTitleMeasurement: (title: String, scale: CGFloat, width: CGFloat)?''')
    s = rep(s, '''        let titleSize = captureLabel.sizeThatFits(CGSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude))
        let size = CGSize(width: ceil(titleSize.width * displayScale) / displayScale, height: titleLabel.bounds.height)''', '''        let pixels = displayScale
        if ngTitleMeasurement?.title != title || ngTitleMeasurement?.scale != pixels {
            let measured = captureLabel.sizeThatFits(CGSize(width: CGFloat.greatestFiniteMagnitude,
                                                            height: CGFloat.greatestFiniteMagnitude)).width
            ngTitleMeasurement = (title, pixels, ceil(measured * pixels) / pixels)
        }
        let size = CGSize(width: ngTitleMeasurement?.width ?? 0, height: titleLabel.bounds.height)''')
    s = rep(s, '        captureLabel.text = item.title\n',
            '        if captureLabel.text != item.title { ngTitleMeasurement = nil }\n        captureLabel.text = item.title\n')
    s = rep(s, '                self.updateEdgeLayers()\n            }\n            self.refreshVibrantTints()\n            self.rebuildChromeCapture()',
            '                self.updateEdgeLayers(rebuildCapture: false)\n            }\n            self.refreshVibrantTints()\n            self.rebuildChromeCapture()')
    s = rep(s, '    private func updateEdgeLayers() {', '    private func updateEdgeLayers(rebuildCapture: Bool = true) {')
    s = rep(s, '        barEdgeGlowLayer.contents = images.glow\n        rebuildChromeCapture()',
            '        barEdgeGlowLayer.contents = images.glow\n        if rebuildCapture { rebuildChromeCapture() }')
    # A translated lens does not need a new drawable or a new blur kernel.
    a = s.index('    private func placeLens(at containerFrame: CGRect) {')
    b = s.index('    private func setLensFill(', a)
    lens = s[a:b]
    lens = rep(lens, '''        glassView.bounds = CGRect(origin: .zero, size: resting)
        glassView.center = CGPoint(x: containerFrame.midX, y: containerFrame.midY)''', '''        let bounds = CGRect(origin: .zero, size: resting)
        let center = CGPoint(x: containerFrame.midX, y: containerFrame.midY)
        if glassView.bounds != bounds { glassView.bounds = bounds }
        if glassView.center != center { glassView.center = center }''')
    lens = rep(lens, '''        shape.widthInset = (resting.width - containerFrame.width) / 2 - outset
        shape.heightInset = (resting.height - containerFrame.height) / 2 - outset
        shape.cornerRadius = lensCornerRadius(forHeight: containerFrame.height + 2 * outset)''', '''        let insetX = (resting.width - containerFrame.width) / 2 - outset
        let insetY = (resting.height - containerFrame.height) / 2 - outset
        let radius = lensCornerRadius(forHeight: containerFrame.height + 2 * outset)
        guard shape.widthInset != insetX || shape.heightInset != insetY || shape.cornerRadius != radius else { return }
        shape.widthInset = insetX
        shape.heightInset = insetY
        shape.cornerRadius = radius''')
    return s[:a] + lens + s[b:]


def drag_renderer(s, rep):
    s = rep(s, '    var ngNonblockingRendering = false', '''    var ngNonblockingRendering = false
    // CAMetalLayer acquisition can wait for the compositor. Keep the one
    // outstanding acquisition off the UI thread; all live view sampling and
    // encoding of its latest coordinates still happen on the main thread.
    private let ngDrawableQueue = DispatchQueue(label: "com.ning.theseus.drawable", qos: .userInitiated)
    private var ngDrawableEpoch: UInt64 = 0
    private var ngDrawablePending = false
    private var ngReadyDrawable: CAMetalDrawable?

    private func ngPrefetchDrawable(_ layer: CAMetalLayer) {
        guard !ngDrawablePending, ngReadyDrawable == nil,
              layer.drawableSize.width > 0, layer.drawableSize.height > 0 else { return }
        ngDrawablePending = true
        let epoch = ngDrawableEpoch
        ngDrawableQueue.async { [weak self, weak layer] in
            let drawable = autoreleasepool { layer?.nextDrawable() }
            DispatchQueue.main.async { [weak self, weak layer] in
                guard let self else { return }
                self.ngDrawablePending = false
                guard self.ngDrawableEpoch == epoch, self.isRendering,
                      let layer, self.metalLayer === layer else { return }
                self.ngReadyDrawable = drawable
            }
        }
    }

    private func ngTakeDrawable(_ layer: CAMetalLayer) -> CAMetalDrawable? {
        let ready = ngReadyDrawable
        ngReadyDrawable = nil
        ngPrefetchDrawable(layer)
        guard let ready,
              abs(CGFloat(ready.texture.width) - layer.drawableSize.width) < 0.5,
              abs(CGFloat(ready.texture.height) - layer.drawableSize.height) < 0.5 else { return nil }
        return ready
    }''')
    s = rep(s, '''        if !ngNonblockingRendering {
            waitForGPUCompletion()
            markAllFramesCompleted()
        }''', '''        if ngNonblockingRendering {
            ngDrawableEpoch &+= 1
            ngReadyDrawable = nil
        } else {
            waitForGPUCompletion()
            markAllFramesCompleted()
        }''')
    s = rep(s, '              let drawable = metalLayer.nextDrawable() else {',
            '              let drawable = (ngNonblockingRendering ? ngTakeDrawable(metalLayer) : metalLayer.nextDrawable()) else {')
    s = rep(s, '                    opaqueBackdrop: (hostView as? TheseusView)?.ngOpaqueBackdrop == true\n',
            '                    opaqueBackdrop: (hostView as? TheseusView)?.ngOpaqueBackdrop == true,\n                    limitCompensation: ngNonblockingRendering\n', count=2)
    return rep(s, '''        NGSystemTabCaptureBegin()
        willCapture?()
        defer { didCapture?(); NGSystemTabCaptureEnd() }''', '''        NGSystemTabCaptureBegin()
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        willCapture?()
        defer {
            didCapture?()
            CATransaction.commit()
            NGSystemTabCaptureEnd()
        }''')


def bounded_compensation(s, rep):
    s = rep(s, '    static func begin(in root: UIView) -> [Entry] {',
            '    static func begin(in root: UIView, region: CGRect?) -> [Entry] {')
    s = rep(s, '        apply(to: root, entries: &entries)',
            '        apply(to: root, in: root, region: region?.insetBy(dx: -2, dy: -2), entries: &entries)')
    s = rep(s, '''    private static func apply(to view: UIView, entries: inout [Entry]) {
        guard !view.isHidden, view.alpha > 0.01 else { return }''', '''    private static func apply(to view: UIView, in root: UIView, region: CGRect?, entries: inout [Entry]) {
        guard !view.isHidden, view.alpha > 0.01 else { return }
        // An unclipped ancestor may have in-range descendants even when its
        // own rect is outside the capture. Prune only proven clipped branches.
        if let region, view !== root, view.clipsToBounds,
           !view.convert(view.bounds, to: root).intersects(region) { return }''')
    return rep(s, '            apply(to: subview, entries: &entries)',
               '            apply(to: subview, in: root, region: region, entries: &entries)')


def bounded_capture(s, rep):
    s = rep(s, '        opaqueBackdrop: Bool = false\n',
            '        opaqueBackdrop: Bool = false,\n        limitCompensation: Bool = false\n')
    return rep(s, 'CaptureCompensation.begin(in: sourceView)',
               'CaptureCompensation.begin(in: sourceView, region: limitCompensation ? region : nil)')


def appearance_tab(s, rep):
    s = rep(s, '        backgroundGlassView.ngInvalidateBackdrop(after: 0)',
            '        backgroundGlassView.ngRefreshPlatter(crossfade: false)')
    s = rep(s, '    private var barEdgeKey: [CGFloat]?',
            '    private var barEdgeKey: [CGFloat]?\n    private var ngAnimateAppearance = false\n    private var ngPalettePending = false')
    s = rep(s, 'edgeLayer.actions = ["bounds": NSNull(), "position": NSNull(), "contents": NSNull()]',
            'edgeLayer.actions = ["bounds": NSNull(), "position": NSNull(), "contents": NSNull(), "hidden": NSNull()]')
    s = rep(s, '        barEdgeShadeLayer.contents = images.shade\n        barEdgeGlowLayer.contents = images.glow', '''        if ngAnimateAppearance {
            for edge in [barEdgeShadeLayer, barEdgeGlowLayer] where edge.contents != nil {
                let fade = CATransition()
                fade.type = .fade
                fade.duration = NGTabPresentation.appearanceDuration
                edge.add(fade, forKey: "ngAppearance")
            }
        }
        barEdgeShadeLayer.contents = images.shade
        barEdgeGlowLayer.contents = images.glow''')
    s = rep(s, '''                resetAdaptation()
                applyAdaptiveOverride()
                updateAdaptiveAppearance()
                updateAppearanceForCurrentMode()
                if !isDragging {
                    updateItemColors()
                }''', '''                let styleChanged = previousTraitCollection.map {
                    $0.userInterfaceStyle != .unspecified && $0.userInterfaceStyle != traitCollection.userInterfaceStyle
                } ?? false
                let animate = ngUseHostPosition && styleChanged && window != nil
                    && !ngHostIsInteracting && TheseusSettings.shared.areMorphAnimationsEnabled
                if ngUseHostPosition && styleChanged {
                    ngPalettePending = backgroundGlassView.ngRefreshPlatter(crossfade: animate) { [weak self] animated in
                        self?.ngFinishHostedPalette(animated: animated)
                    }
                }
                ngAnimateAppearance = animate && !ngPalettePending
                defer { ngAnimateAppearance = false }
                resetAdaptation()
                applyAdaptiveOverride()
                // The last luminance can belong to the opposite appearance.
                // Hosted bars adapt once the new snapshot has arrived instead.
                if !ngUseHostPosition || !styleChanged { updateAdaptiveAppearance() }
                updateAppearanceForCurrentMode()
                if !isDragging {
                    applyItemStates(selectedAt: selectedIndex, animated: ngAnimateAppearance)
                }''')

    s = rep(s, '    private func updateAppearanceForCurrentMode() {\n        let isDark = isDarkAppearance', '''    private func ngFinishHostedPalette(animated: Bool) {
        guard ngPalettePending else { return }
        ngPalettePending = false
        ngAnimateAppearance = animated && window != nil && !ngHostIsInteracting
            && TheseusSettings.shared.areMorphAnimationsEnabled
        defer { ngAnimateAppearance = false }
        updateAppearanceForCurrentMode()
        if !isDragging { applyItemStates(selectedAt: selectedIndex, animated: ngAnimateAppearance) }
    }

    private func updateAppearanceForCurrentMode() {
        let isDark = isDarkAppearance
        if ngUseHostPosition, !ngPalettePending {
            selectionView.ngSetSolidSelectionTone(dark: isDark, animated: ngAnimateAppearance)
        }''')
    s = rep(s, '        let scale = traitCollection.displayScale > 0 ? traitCollection.displayScale : UIScreen.main.scale\n        let amplitude =',
            '        guard !ngPalettePending else { return }\n        let scale = traitCollection.displayScale > 0 ? traitCollection.displayScale : UIScreen.main.scale\n        let amplitude =')
    s = rep(s, '    private func updateBarShadow() {\n',
            '    private func updateBarShadow() {\n        guard !ngPalettePending else { return }\n')
    s = rep(s, '        let colors: [CGColor]\n        let locations: [NSNumber]\n        if usesIOS26Look {',
            '        guard !ngPalettePending else { return }\n        let colors: [CGColor]\n        let locations: [NSNumber]\n        if usesIOS26Look {')
    s = rep(s, '    private func applyItemTints(selectedAt selected: Int, animated: Bool) {\n',
            '    private func applyItemTints(selectedAt selected: Int, animated: Bool) {\n        guard !ngPalettePending else { return }\n')
    s = rep(s, '    private func updateAdaptiveAppearance() {\n',
            '    private func updateAdaptiveAppearance() {\n        guard !ngPalettePending else { return }\n')
    return s


def appearance_surface(s, rep):
    a = s.index('    private var ngSwitchCover: UIView?')
    b = s.index('    func ngPrepareReplacement() {', a)
    s = s[:a] + '''    private let ngAppearanceImage = CALayer()
    private var ngAppearanceSnapshot: CGImage?
    private var ngAppearanceReveal: ((Bool) -> Void)?
    private var ngAppearanceEpoch: UInt64 = 0
    private var ngAppearancePending = false

    // Ordinary page switches leave the already-mounted frosted surface and
    // its feathered edge alone. Only theme switches cross-fade old optics.
    @discardableResult
    func ngRefreshPlatter(crossfade: Bool, onReveal: ((Bool) -> Void)? = nil) -> Bool {
        guard !ngSolidSelection else { return false }
        ngBackdropEpoch &+= 1
        var held = false
        if crossfade, ngPresented, !isUsingFallback, let renderer, let metal = metalLayerView,
           let image = captureSnapshot ?? ngAppearanceSnapshot,
           !bounds.isEmpty, !metal.isHidden {
            ngAppearanceEpoch &+= 1
            let epoch = ngAppearanceEpoch
            held = true
            ngAppearancePending = true
            ngAppearanceSnapshot = image
            ngAppearanceReveal = onReveal
            CATransaction.begin()
            CATransaction.setDisableActions(true)
            ngAppearanceImage.removeAllAnimations()
            ngAppearanceImage.frame = captureSnapshotFrame
            ngAppearanceImage.contentsGravity = .resize
            ngAppearanceImage.contents = image
            ngAppearanceImage.opacity = 1
            if ngAppearanceImage.superlayer == nil { layer.insertSublayer(ngAppearanceImage, above: metal.layer) }
            CATransaction.commit()
            renderer.ngVisiblePresent = { [weak self] in self?.ngFinishPlatterAppearance(epoch) }
            // The compositor can skip a presentation while an overlay is up.
            // Never leave a stale appearance image hanging on the screen.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
                self?.ngFinishPlatterAppearance(epoch)
            }
        } else if onReveal != nil {
            ngClearPlatterAppearance(notify: false)
        }
        captureSnapshot = nil
        captureSnapshotOverride = nil
        ngConfigurePresentCallback()
        applySnapshotSetting()
        renderer?.setNeedsRender()
        return held
    }

    private func ngFinishPlatterAppearance(_ epoch: UInt64) {
        guard ngAppearancePending, ngAppearanceEpoch == epoch else { return }
        ngAppearancePending = false
        renderer?.ngVisiblePresent = nil
        let reveal = ngAppearanceReveal
        ngAppearanceReveal = nil
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        CATransaction.setCompletionBlock { [weak self] in
            guard let self, self.ngAppearanceEpoch == epoch else { return }
            self.ngAppearanceImage.removeFromSuperlayer()
            self.ngAppearanceImage.contents = nil
            self.ngAppearanceSnapshot = nil
        }
        ngAppearanceImage.opacity = 0
        let fade = CABasicAnimation(keyPath: "opacity")
        fade.fromValue = 1
        fade.toValue = 0
        fade.duration = NGTabPresentation.appearanceDuration
        fade.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
        ngAppearanceImage.add(fade, forKey: "ngAppearance")
        CATransaction.commit()
        reveal?(true)
    }

    private func ngClearPlatterAppearance(notify: Bool = true) {
        ngAppearanceEpoch &+= 1
        ngAppearancePending = false
        renderer?.ngVisiblePresent = nil
        ngAppearanceImage.removeAllAnimations()
        ngAppearanceImage.removeFromSuperlayer()
        ngAppearanceImage.contents = nil
        ngAppearanceSnapshot = nil
        let reveal = ngAppearanceReveal
        ngAppearanceReveal = nil
        if notify { reveal?(false) }
    }

''' + s[b:]
    s = rep(s, '    private var ngCaptureNotBefore: CFTimeInterval = 0\n', '')
    s = rep(s, '        renderer?.ngCaptureNotBefore = ngCaptureNotBefore\n', '')
    s = rep(s, '        ngSwitchCover?.isHidden = true\n', '', count=2)
    s = rep(s, '            ngSwitchCover?.layer.removeAllAnimations()\n', '            ngClearPlatterAppearance()\n')
    a = s.index('            if let cover = ngSwitchCover, !cover.isHidden, cover.alpha > 0 {')
    b = s.index('        }\n        onPresent?()', a)
    s = s[:a] + s[b:]
    s = rep(s, '''        if let cover = ngSwitchCover {
            cover.frame = bounds
            cover.layer.cornerRadius = shape.cornerRadius
        }''', '''        if ngAppearanceImage.superlayer != nil { ngAppearanceImage.frame = captureSnapshotFrame }''')
    s = rep(s, '''        } else {
            renderer?.stopRendering()
            renderer = nil
        }''', '''        } else {
            ngClearPlatterAppearance()
            renderer?.stopRendering()
            renderer = nil
        }''')
    s = rep(s, '    private var ngSolidSelection = false',
            '    private var ngSolidSelection = false\n    private var ngSolidSelectionDark = false')
    s = rep(s, '        ngSolidSelection = true\n',
            '        ngSolidSelection = true\n        ngSolidSelectionDark = traitCollection.userInterfaceStyle == .dark\n')
    s = rep(s, '''    private func ngUpdateSolidSelection() {
        let tone: CGFloat = traitCollection.userInterfaceStyle == .dark ? 0.26 : 0.88''', '''    func ngSetSolidSelectionTone(dark: Bool, animated: Bool) {
        guard ngSolidSelection, ngSolidSelectionDark != dark else { return }
        ngSolidSelectionDark = dark
        ngUpdateSolidSelection(animated: animated)
    }

    private func ngUpdateSolidSelection(animated: Bool = false) {
        let tone: CGFloat = ngSolidSelectionDark ? 0.26 : 0.88''')
    s = rep(s, '''        backgroundColor = UIColor(white: tone, alpha: 1)
        layer.cornerRadius = shape.cornerRadius
        CATransaction.commit()''', '''        let fill = UIColor(white: tone, alpha: 1)
        let previous = layer.presentation()?.backgroundColor ?? layer.backgroundColor
        let changed = backgroundColor != fill
        backgroundColor = fill
        layer.cornerRadius = shape.cornerRadius
        if changed, let previous, animated, window != nil {
            let fade = CABasicAnimation(keyPath: "backgroundColor")
            fade.fromValue = previous
            fade.toValue = fill.cgColor
            fade.duration = NGTabPresentation.appearanceDuration
            fade.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            layer.add(fade, forKey: "ngPillAppearance")
        }
        CATransaction.commit()''')
    return s


def appearance_renderer(s, rep):
    s = rep(s, '    var ngCaptureNotBefore: CFTimeInterval = 0', '    var ngVisiblePresent: (() -> Void)?')
    s = rep(s, '        guard CACurrentMediaTime() >= ngCaptureNotBefore, shouldRender() else { return }',
            '        guard shouldRender() else { return }')
    return rep(s, '        let presentsWithTransaction = metalLayer.presentsWithTransaction\n', '''        if let visiblePresent = ngVisiblePresent {
            drawable.addPresentedHandler { shown in
                guard shown.presentedTime > 0 else { return }
                DispatchQueue.main.async(execute: visiblePresent)
            }
        }
        let presentsWithTransaction = metalLayer.presentsWithTransaction
''')

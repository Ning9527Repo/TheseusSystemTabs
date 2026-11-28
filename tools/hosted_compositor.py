"""Keep the hosted platter fixed and use the normal Theseus page lens."""


def tab(s, rep):
    s = rep(s, '    private func ngSyncPlatterHold() {\n        if ngUseHostPosition { backgroundGlassView.ngHoldBackdrop(ngHostIsInteracting) }\n    }', '''    private lazy var ngHostedPlatter = UIVisualEffectView(effect: UIBlurEffect(style: .systemChromeMaterialLight))

    private func ngInstallHostedChrome() {
        // Use one fixed light blur plus an independently tinted surface. The
        // blur is never rebuilt or retargeted when the host's traits change.
        backgroundGlassView.snapshotDidUpdate = nil
        backgroundGlassView.providesCaptureSnapshot = false
        backgroundGlassView.pauseRendering()
        backgroundGlassView.removeFromSuperview()
        resetAdaptation()
        contentView.overrideUserInterfaceStyle = .unspecified
        selectionView.ngEnableSolidSelection()
        pillShadeLayer.removeFromSuperlayer()
        ngHostedPlatter.overrideUserInterfaceStyle = .light
        ngHostedPlatter.isUserInteractionEnabled = false
        ngHostedPlatter.clipsToBounds = true
        backgroundView.insertSubview(ngHostedPlatter, at: 0)
        ngApplyHostedAppearance(animated: false)
    }

    private func ngSetHostedColor(_ color: CGColor, on target: CALayer, key: String, animated: Bool) {
        let old: CGColor? = key == "borderColor" ? target.borderColor : target.backgroundColor
        guard old != color else { return }
        let live = target.presentation()
        let shown = (key == "borderColor" ? live?.borderColor : live?.backgroundColor) ?? old
        target.removeAnimation(forKey: "ngHosted." + key)
        if key == "borderColor" { target.borderColor = color }
        else { target.backgroundColor = color }
        if animated, let shown {
            let fade = CABasicAnimation(keyPath: key)
            fade.fromValue = shown
            fade.toValue = color
            fade.duration = NGTabPresentation.appearanceDuration
            fade.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            target.add(fade, forKey: "ngHosted." + key)
        }
    }

    private func ngApplyHostedAppearance(animated: Bool) {
        let dark = systemIsDark
        let reduce = UIAccessibility.isReduceTransparencyEnabled
        let tint = UIColor(white: dark ? 0.04 : 1, alpha: reduce ? 1 : (dark ? 0.76 : 0.22))
        let animate = animated && window != nil && !UIAccessibility.isReduceMotionEnabled
            && TheseusSettings.shared.areMorphAnimationsEnabled
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        ngAnimateAppearance = animate
        adaptDarkWeight = dark ? 1 : 0
        adaptDarkTarget = adaptDarkWeight
        ngSetHostedColor(tint.cgColor, on: ngHostedPlatter.contentView.layer, key: "backgroundColor", animated: animate)
        selectionView.ngSetSolidSelectionTone(dark: dark, animated: animate)
        // Keep one opaque selection surface; the old simultaneous lens/pill
        // compositing and its second outline are not used in hosted gestures.
        selectionView.layer.borderWidth = 0
        selectionView.layer.borderColor = nil
        updateEdgeLayers(rebuildCapture: false)
        updateBarShadow()
        applyItemTints(selectedAt: selectedIndex, animated: animate)
        ngAnimateAppearance = false
        CATransaction.commit()
    }''')
    for signature in ('setBarLifted(_ lifted: Bool)', 'applyBarBodyGain(progress: CGFloat)', 'applyBarTransform()'):
        header = '    private func ' + signature + ' {\n'
        if header in s:
            s = rep(s, header, header + '        guard !ngUseHostPosition else { return }\n')
    s = rep(s, '''            backgroundGlassView.ngFrostedPlatter = ngUseHostPosition
            var chrome = backgroundGlassView.configuration
            chrome.blur.radius = ngUseHostPosition ? 26 : 18
            chrome.blur.sigma = ngUseHostPosition ? 9 : nil
            chrome.refraction.interiorSharpness = ngUseHostPosition ? 0 : Self.chromeDetailLight
            backgroundGlassView.configuration = chrome
            backgroundGlassView.ngOpaqueBackdrop = ngUseHostPosition
            if ngUseHostPosition { selectionView.ngEnableSolidSelection() }''',
            '            if ngUseHostPosition && !oldValue { ngInstallHostedChrome() }')
    s = rep(s, '''        backgroundGlassView.ngPrepareReplacement()
        if !ngUseHostPosition { selectionView.ngPrepareReplacement() }''',
            '''        if ngUseHostPosition { return }
        backgroundGlassView.ngPrepareReplacement()
        selectionView.ngPrepareReplacement()''')
    s = rep(s, '    private func ngInvalidatePageFrames() {\n',
            '    private func ngInvalidatePageFrames() {\n        guard !ngUseHostPosition else { return }\n')
    s = rep(s, '    public func invalidateBackground() {\n',
            '    public func invalidateBackground() {\n        guard !ngUseHostPosition else { return }\n')
    a = s.index('        backgroundGlassView.frame = bodyFrame\n')
    b = s.index('        updateBarShadow()', a)
    regular = s[a:b]
    s = s[:a] + '''        if ngUseHostPosition {
            CATransaction.begin()
            CATransaction.setDisableActions(true)
            ngHostedPlatter.frame = bodyFrame
            ngHostedPlatter.layer.cornerRadius = bodyFrame.height / 2
            CATransaction.commit()
            updateEdgeLayers(rebuildCapture: false)
        } else {
''' + ''.join('    ' + line if line.strip() else line for line in regular.splitlines(keepends=True)) + '        }\n' + s[b:]
    s = rep(s, '''        super.traitCollectionDidChange(previousTraitCollection)
        if #available(iOS 13.0, *) {''', '''        super.traitCollectionDidChange(previousTraitCollection)
        if ngUseHostPosition {
            if traitCollection.hasDifferentColorAppearance(comparedTo: previousTraitCollection) {
                ngApplyHostedAppearance(animated: previousTraitCollection != nil)
            }
            return
        }
        if #available(iOS 13.0, *) {''')
    s = rep(s, '    private func updateAppearanceForCurrentMode() {\n',
            '    private func updateAppearanceForCurrentMode() {\n        if ngUseHostPosition { ngApplyHostedAppearance(animated: false); return }\n')
    s = rep(s, '    private func updatePillShade(size: CGSize) {\n',
            '    private func updatePillShade(size: CGSize) {\n        guard !ngUseHostPosition else { return }\n')
    s = rep(s, '''        if isDragging {
            endDragImmediately()
        }
        contentView.bringSubviewToFront(container)''', '''        if isDragging || (ngUseHostPosition && isCollapsingLens) { endDragImmediately() }
        contentView.bringSubviewToFront(container)''')
    s = rep(s, 'showsSelectedIcon: isSelected && !isDragging,',
            'showsSelectedIcon: isSelected && !(ngUseHostPosition && isDragging),')
    s = rep(s, '        let restingTint = vibrantTint(selectedTintColor, over: selectionView.renderedCenterColor ?? selectionView.captureVeilColor)\n', '''        let hostedTint = ngUseHostPosition
            ? selectedTintColor.resolvedColor(with: UITraitCollection(userInterfaceStyle: .light))
            : nil
        let restingTint = hostedTint ?? vibrantTint(selectedTintColor, over: selectionView.renderedCenterColor ?? selectionView.captureVeilColor)
''')
    s = rep(s, '''        appliedRestingTint = restingTint
        let lensTint = vibrantTint(selectedTintColor, over: lensBackdropColor, plus: lensTintBrightening)
''', '''        appliedRestingTint = restingTint
        let lensTint = hostedTint ?? vibrantTint(selectedTintColor, over: lensBackdropColor, plus: lensTintBrightening)
''')
    s = rep(s, '''    private func updateHoveredItem(lensCenterX: CGFloat) {
        guard isDragging, !itemViews.isEmpty else { return }''', '''    private func updateHoveredItem(lensCenterX: CGFloat) {
        guard !ngUseHostPosition, isDragging, !itemViews.isEmpty else { return }''')
    s = rep(s, '    @objc private func theseusSettingsDidChange() {\n', '''    @objc private func theseusSettingsDidChange() {
        if ngUseHostPosition {
            ngApplyHostedAppearance(animated: false)
            invalidateIntrinsicContentSize()
            setNeedsLayout()
            return
        }
''')
    s = rep(s, '''        super.didMoveToWindow()
        if window == nil {
            teardownTheseus()''', '''        super.didMoveToWindow()
        if ngUseHostPosition {
            if window == nil { endDragImmediately() }
            else { ngApplyHostedAppearance(animated: false) }
            return
        }
        if window == nil {
            teardownTheseus()''')
    # Keep the pill and live item row as separate layers above the lens.
    s = rep(s, '\n        container.addSubview(glassView)\n', '''
        if ngUseHostPosition {
            contentView.insertSubview(glassView, aboveSubview: selectionView)
            contentView.bringSubviewToFront(glassView)
        } else { container.addSubview(glassView) }
''')
    s = rep(s, '\n            container.addSubview(glassView)\n', '''
            if ngUseHostPosition {
                contentView.insertSubview(glassView, aboveSubview: selectionView)
                contentView.bringSubviewToFront(glassView)
            } else { container.addSubview(glassView) }
''')
    s = rep(s, '        glassView.resumeRendering()\n', '''        if ngUseHostPosition { contentView.bringSubviewToFront(glassView) }
        glassView.resumeRendering()
''')
    a = s.index('        glassView.captureWillBegin =')
    b = s.index('    private func showTheseus()', a)
    b = s.rindex('    }\n', a, b)
    callbacks = s[a:b]
    s = s[:a] + callbacks + s[b:]
    s = rep(s, '        guard !isDragging, isUserInteractionEnabled else { return }\n', '''        guard !isDragging, isUserInteractionEnabled else { return }
        if ngUseHostPosition {
            guard rawX.isFinite, slotFrames.indices.contains(selectedIndex) else { return }
            let pressed = findClosestItemIndex(to: CGPoint(x: rawX, y: 0))
            guard items.indices.contains(pressed), items[pressed].ngEnabled else { return }
        }
''')
    s = rep(s, '        isDragging = true\n        ngFollowFrame = nil\n        let anchorX', '''        isDragging = true
        ngFollowFrame = nil
        if ngUseHostPosition {
            selectionView.layer.removeAllAnimations()
            selectionView.alpha = 0
            selectionView.isHidden = true
            applyItemTints(selectedAt: selectedIndex, animated: false)
        }
        let anchorX''')
    s = rep(s, '        selectionAnimator?.rest(at: restingCenterX, immediate: ngUseHostPosition)\n\n        showTheseus()', '''        showTheseus()
        selectionAnimator?.rest(at: restingCenterX, immediate: ngUseHostPosition)''')
    s = rep(s, '        guard isDragging else { return }\n        let landingIndex', '''        guard isDragging else { return }
        if ngUseHostPosition && !rawX.isFinite { endDragImmediately(); return }
        let landingIndex''')
    s = rep(s, '        selectionAnimator?.follow(x: location.x', '''        if ngUseHostPosition && (!isDragging || !location.x.isFinite) { return }
        selectionAnimator?.follow(x: location.x''')
    s = rep(s, '        setLensRefraction(1)\n        updateItemColors()', '''        setLensRefraction(1)
        if ngUseHostPosition {
            ngFollowFrame = nil
            updateSelectionViewFrame(animated: false)
        }
        updateItemColors()''')
    s = rep(s, '            self.selectionView.layer.transform = LensMorph.transform(mapping: pillLocal, onto: localFrame)', '''            if !self.ngUseHostPosition {
                self.selectionView.layer.transform = LensMorph.transform(mapping: pillLocal, onto: localFrame)
            }''')
    s = rep(s, '                    if self.isPillFading, !self.selectionView.isHidden {',
            '                    if !self.ngUseHostPosition, self.isPillFading, !self.selectionView.isHidden {')
    s = rep(s, '        fadePill(to: 0, spring: Self.pillFadeOutSpring)', '''        if ngUseHostPosition {
            pillFadeDriver.stop()
            isPillFading = false
            selectionView.alpha = 0
            selectionView.isHidden = true
        } else {
            fadePill(to: 0, spring: Self.pillFadeOutSpring)
        }''')
    s = rep(s, '        glassView.setCaptureExcludedViews([ngExcludedBar, selectionView].compactMap { $0 })',
            '        glassView.setCaptureExcludedViews([ngExcludedBar, selectionView].compactMap { $0 })')
    s = rep(s, '''                    self.placeLens(at: containerFrame)
                    if !self.ngUseHostPosition, self.isPillFading, !self.selectionView.isHidden {''', '''                    self.placeLens(at: containerFrame)
                    if !self.ngUseHostPosition, self.isPillFading, !self.selectionView.isHidden {''')
    return s

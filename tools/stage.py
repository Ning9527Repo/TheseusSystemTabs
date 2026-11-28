#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import sys

import hosted_appearance
import hosted_compositor
import hosted_motion
import platter_edges
import stability

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'Vendor/Theseus'


def verify_vendor():
    expected = json.loads((ROOT/'Vendor/manifest.json').read_text())['files']
    actual = {str(p.relative_to(VENDOR)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(VENDOR.rglob('*')) if p.is_file()}
    if actual != expected:
        raise SystemExit('Theseus vendor manifest mismatch')


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise SystemExit(f'Patch anchor mismatch: {old!r}')
    return text.replace(old, new)


def tabbar(s):
    s = replace(s, '    public var selectedIndex: Int = 0 {', '''    weak var ngExcludedBar: UIView?
    var ngActivateNative: ((Int) -> Int?)?
    var ngUseHostPosition = false {
        didSet {
            backgroundGlassView.ngOpaqueBackdrop = ngUseHostPosition
            selectionView.ngOpaqueBackdrop = ngUseHostPosition
            selectionView.ngSelectionBackdrop = ngUseHostPosition
        }
    }

    var ngHostFrame = CGRect.zero
    var ngGlassDidPresent: (() -> Void)? {
        didSet { backgroundGlassView.onPresent = ngGlassDidPresent }
    }

    func ngPrepareReplacement() {
        backgroundGlassView.ngPrepareReplacement()
        selectionView.ngPrepareReplacement()
    }

    var ngHostIsInteracting: Bool { isDragging || isCollapsingLens }

    private var ngRefreshingItems = false

    func ngRefreshItems(_ refreshed: [TheseusTabBarItem], changed: [Int]) {
        guard itemViews.count == refreshed.count else { items = refreshed; return }
        ngRefreshingItems = true
        items = refreshed
        ngRefreshingItems = false
        for i in changed {
            let selected = i == selectedIndex
            itemViews[i].configure(with: items[i], isSelected: selected)
            itemViews[i].tintColor = selected ? (appliedRestingTint ?? selectedTintColor) : unselectedTint()
        }
    }

    func ngApplySelection(_ index: Int) {
        guard index != selectedIndex else { return }
        if isCollapsingLens { endDragImmediately() }
        selectedIndex = index
    }

    func ngApplyHostFrame(_ next: CGRect) {
        if isDragging || isCollapsingLens { endDragImmediately() }
        ngHostFrame = next
        frame = next
        setNeedsLayout()
        invalidateBackground()
    }

    public var selectedIndex: Int = 0 {''')
    s = replace(s, '    public var title: String?\n', '''    public var title: String?
    var ngBadge: String?
    var ngBadgeColor: UIColor?
    var ngLabel: String?
    var ngEnabled = true
''')
    s = replace(s, '            rebuildItemViews()\n            setNeedsLayout()', '            guard !ngRefreshingItems else { return }\n            rebuildItemViews()\n            setNeedsLayout()')
    s = replace(s, '        let contentWidth = min(bounds.width,', '        if ngUseHostPosition { return bounds }\n        let contentWidth = min(bounds.width,')
    s = replace(s, '        let barFrame = contentBarFrame.insetBy(dx: barContentInset, dy: 0)',
                '        let barFrame = ngUseHostPosition ? NGTabPresentation.slotStrip(platter: backgroundView.frame) : contentBarFrame.insetBy(dx: barContentInset, dy: 0)')
    s = replace(s, '        let size = pillSize\n', '''        if ngUseHostPosition { return NGTabPresentation.capsule(slot: itemFrame) }
        let size = pillSize
''')
    s = replace(s, '        let size = usesIOS26Look ? Self.iOS26LensSize : Self.lensSize\n', '''        let original = usesIOS26Look ? Self.iOS26LensSize : Self.lensSize
        // Retain the original press expansion on wider system tab slots.
        let size = ngUseHostPosition
            ? CGSize(width: selectionFrame(for: itemFrame).width + original.width - pillSize.width, height: original.height)
            : original
''')
    s = replace(s, '            UIView.animate(withDuration: 0.22, delay: 0, usingSpringWithDamping: 0.88, initialSpringVelocity: 0.75) {', '''            let options: UIView.AnimationOptions = ngUseHostPosition ? [.beginFromCurrentState, .allowUserInteraction] : []
            UIView.animate(withDuration: 0.22, delay: 0, usingSpringWithDamping: 0.88,
                           initialSpringVelocity: 0.75, options: options) {
'''.rstrip('\n'))
    s = replace(s, '    private func selectItem(at index: Int) {\n', '''    private func selectItem(at index: Int) {
        if ngUseHostPosition {
            guard items.indices.contains(index), items[index].ngEnabled,
                  let confirmed = ngActivateNative?(index), items.indices.contains(confirmed) else { return }
            if isCollapsingLens, confirmed != selectedIndex { endDragImmediately() }
            selectedIndex = confirmed
            return
        }
''')
    s = replace(s, '        guard index != selectedIndex else { return }\n        selectedIndex = index', '        guard items.indices.contains(index), items[index].ngEnabled, index != selectedIndex else { return }\n        selectedIndex = index')
    s = replace(s, '        super.layoutSubviews()\n\n        contentView.bounds = bounds', '''        super.layoutSubviews()

        let exclusions = [self, ngExcludedBar].compactMap { $0 }
        backgroundGlassView.setCaptureExcludedViews(exclusions)
        selectionView.setCaptureExcludedViews(exclusions)
        if let bar = ngExcludedBar { theseusView?.setCaptureExcludedViews([bar]) }
        contentView.bounds = bounds''')
    s = replace(s, '            CGRect(x: barFrame.minX + CGFloat(index) * itemWidth, y: 0, width: itemWidth, height: itemHeight)', '''            let rtl = ngUseHostPosition && effectiveUserInterfaceLayoutDirection == .rightToLeft
            let slot = rtl ? itemViews.count - index - 1 : index
            return CGRect(x: barFrame.minX + CGFloat(slot) * itemWidth, y: ngUseHostPosition ? barFrame.minY : 0, width: itemWidth, height: itemHeight)''')
    s = replace(s, '        theseusSourceView?.superview\n', '        ngUseHostPosition ? contentView : theseusSourceView?.superview\n')
    s = replace(s, '''        config.refraction.magnificationCenterY = 0
        config.refraction.intensity = 1.1
        config.edgeEffects.rimGlow = 0
        config.edgeEffects.glareIntensity = 0
''', '''        config.refraction.magnificationCenterY = 0
        config.refraction.intensity = 1.1
        config.edgeEffects.rimGlow = 0.25
        config.edgeEffects.glareIntensity = 0.12
''')
    s = replace(s, '        material.apply(to: &config, isDark: isDarkAppearance, activity: activity)\n', '''        material.apply(to: &config, isDark: isDarkAppearance, activity: activity)
        if ngUseHostPosition { config.refraction.interiorSharpness = min(config.refraction.interiorSharpness, 0.82) }
''')
    s = replace(s, '        glassView.sourceView = sourceView\n        glassView.isHidden', '''        glassView.sourceView = sourceView
        glassView.ngNonblockingRendering = ngUseHostPosition
        glassView.ngCaptureScale = ngUseHostPosition ? 0.5 : 1
        glassView.setCaptureExcludedViews([ngExcludedBar, selectionView].compactMap { $0 })
        glassView.isHidden''')
    s = replace(s, '        case .ended, .cancelled, .failed:\n            finishInteraction(rawX: gesture.location(in: self).x)', '''        case .ended:
            finishInteraction(rawX: gesture.location(in: self).x)
        case .cancelled, .failed:
            if isDragging { endDragImmediately() }''')
    s = replace(s, '        case .ended, .cancelled:\n            finishInteraction(rawX: gesture.location(in: self).x)', '''        case .ended:
            finishInteraction(rawX: gesture.location(in: self).x)
        case .cancelled, .failed:
            if isDragging { endDragImmediately() }''')
    s = replace(s, '''        if landingIndex != selectedIndex {
            isCommittingDrag = true
            selectedIndex = landingIndex
            isCommittingDrag = false
            onItemSelected?(landingIndex)
        }''', '''        if items.indices.contains(landingIndex), items[landingIndex].ngEnabled {
            if ngUseHostPosition {
                if let confirmed = ngActivateNative?(landingIndex), items.indices.contains(confirmed) {
                    isCommittingDrag = true
                    selectedIndex = confirmed
                    isCommittingDrag = false
                }
            } else if landingIndex != selectedIndex {
                isCommittingDrag = true
                selectedIndex = landingIndex
                isCommittingDrag = false
                onItemSelected?(landingIndex)
            }
        }''')
    s = replace(s, '            if landingIndex < self.slotFrames.count {\n                animator?.retarget(to: self.convertToTheseusContainer(self.selectionFrame(for: self.slotFrame(at: landingIndex))))', '''            let target = self.ngUseHostPosition ? self.selectedIndex : landingIndex
            if self.slotFrames.indices.contains(target) {
                animator?.retarget(to: self.convertToTheseusContainer(self.selectionFrame(for: self.slotFrame(at: target))))''')
    s = replace(s, '        NSLayoutConstraint.activate([\n            stackView.centerXAnchor', '        NSLayoutConstraint.activate([\n            stackView.widthAnchor.constraint(lessThanOrEqualTo: widthAnchor, constant: -4),\n            stackView.centerXAnchor')
    s = replace(s, '    private let captureTitleView = UIImageView()', '''    private let captureTitleView = UIImageView()
    private let ngBadgeLabel = UILabel()
    private let ngTwinBadge = UILabel()

    private func ngLayoutBadge(_ label: UILabel, beside icon: CGRect, width: CGFloat) {
        guard !label.isHidden else { return }
        let textWidth: CGFloat = label.sizeThatFits(CGSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat(16))).width
        let w: CGFloat = min(max(16, textWidth + 8), max(16, width - 4))
        let end: CGFloat = min(width - 1, icon.midX + 9 + w / 2)
        label.frame = CGRect(x: max(0, end - w), y: max(0, icon.minY - 2), width: w, height: 16)
    }''')
    s = replace(s, '        captureTwin.addSubview(captureTitleView)', '''        captureTwin.addSubview(captureTitleView)
        for label in [ngBadgeLabel, ngTwinBadge] {
            label.font = .systemFont(ofSize: 10, weight: .semibold)
            label.textAlignment = .center
            label.textColor = .white
            label.layer.cornerRadius = 8
            label.clipsToBounds = true
            label.isHidden = true
            label.isAccessibilityElement = false
        }
        addSubview(ngBadgeLabel)
        captureTwin.addSubview(ngTwinBadge)''')
    s = replace(s, '        iconImageView.transform = transform\n', '        iconImageView.transform = transform\n        ngLayoutBadge(ngBadgeLabel, beside: iconImageView.frame, width: bounds.width)\n')
    s = replace(s, '        accessibilityLabel = item.title ?? item.icon?.accessibilityLabel', '''        accessibilityLabel = item.ngLabel ?? item.title ?? item.icon?.accessibilityLabel
        accessibilityValue = item.ngBadge
        let hasBadge = item.ngBadge?.isEmpty == false
        for label in [ngBadgeLabel, ngTwinBadge] {
            label.text = item.ngBadge
            label.backgroundColor = item.ngBadgeColor ?? .systemRed
            label.isHidden = !hasBadge
        }
        alpha = item.ngEnabled ? 1 : 0.48''')
    s = replace(s, '        captureTitleView.isHidden = titleLabel.isHidden\n', '''        captureTitleView.isHidden = titleLabel.isHidden
        ngLayoutBadge(ngTwinBadge, beside: captureIconView.frame, width: captureTwin.bounds.width)
''')
    s = replace(s, '        return image.withRenderingMode(.alwaysTemplate)\n', '        return image.renderingMode == .alwaysOriginal ? image : image.withRenderingMode(.alwaysTemplate)\n')
    s = replace(s, '        let bitmap = UIGraphicsImageRenderer(size: image.size, format: format).image { _ in\n', '        if image.renderingMode == .alwaysOriginal { return image }\n        let bitmap = UIGraphicsImageRenderer(size: image.size, format: format).image { _ in\n')
    return s


def renderer(s):
    s = replace(s, '        let viewFrame = metalLayer.frame\n', '        let viewFrame = hostView?.bounds ?? metalLayer.frame\n')
    s = replace(s, '              let superlayer = metalLayer.superlayer else {',
                '              let superlayer = hostView?.layer ?? metalLayer.superlayer else {')
    s = replace(s, '                    excludedViews: excludedViews\n', '''                    excludedViews: excludedViews,\n                    opaqueBackdrop: (hostView as? TheseusView)?.ngOpaqueBackdrop == true\n'''.rstrip('\n') + '\n', count=2)
    s = replace(s, '        willCapture?()\n        defer { didCapture?() }', '        NGSystemTabCaptureBegin()\n        willCapture?()\n        defer { didCapture?(); NGSystemTabCaptureEnd() }')
    return replace(s, '            commandBuffer.addCompletedHandler { _ in\n                DispatchQueue.main.async(execute: onPresent)', '            commandBuffer.addCompletedHandler { buffer in\n                guard buffer.status == .completed else { return }\n                DispatchQueue.main.async(execute: onPresent)')


def surface(s):
    s = replace(s, '    public var onPresent: (() -> Void)? {\n        didSet { renderer?.onPresent = onPresent }\n    }', '''    var ngOpaqueBackdrop = false
    private var ngWaitingForPresent = false
    private var ngPresented = false

    func ngPrepareReplacement() {
        ngWaitingForPresent = !ngPresented
        guard ngWaitingForPresent else { return }
        if fallbackView == nil {
            let fallback = VisualEffectFallbackView()
            fallback.isUserInteractionEnabled = false
            fallback.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            fallback.frame = bounds
            insertSubview(fallback, at: 0)
            fallbackView = fallback
        }
        fallbackView?.configure(with: configuration)
        fallbackView?.updateForTraitCollection(traitCollection)
        fallbackView?.isHidden = false
        ngConfigurePresentCallback()
    }

    private func ngConfigurePresentCallback() {
        if ngWaitingForPresent || onPresent != nil {
            renderer?.onPresent = { [weak self] in self?.ngFramePresented() }
        } else { renderer?.onPresent = nil }
    }

    private func ngFramePresented() {
        ngPresented = true
        ngWaitingForPresent = false
        if !isUsingFallback { fallbackView?.isHidden = true }
        onPresent?()
        ngConfigurePresentCallback()
    }

    public var onPresent: (() -> Void)? {
        didSet { ngConfigurePresentCallback() }
    }''')
    s = replace(s, '        renderer?.onPresent = onPresent\n', '        ngConfigurePresentCallback()\n')
    s = replace(s, '            fallbackView?.isHidden = true\n\n            metalLayerView?.isHidden = false', '            fallbackView?.isHidden = !ngWaitingForPresent\n\n            metalLayerView?.isHidden = false')
    # Match drawable geometry to the padded Metal texture. Keep the shader's
    # logical host bounds and account for padding exactly once in capture.
    s = replace(s, '        return (metalLayerView?.frame ?? bounds).insetBy(dx: -padding.x, dy: -padding.y)', '        return bounds.insetBy(dx: -padding.x, dy: -padding.y)')
    s = replace(s, '        metalLayer.contentsGravity = .center', '        metalLayer.contentsGravity = .resize')
    return replace(s, '        let paddingX = padding.x * scale\n', '        metalLayerView?.frame = bounds.insetBy(dx: -padding.x, dy: -padding.y)\n        let paddingX = padding.x * scale\n')


def opaque_capture(s, rect):
    s = replace(s, '        excludedViews: [UIView] = []\n',
                '        excludedViews: [UIView] = [],\n        opaqueBackdrop: Bool = false\n')
    line = '        ctx.clear(' + rect + ')\n'
    return replace(s, line, line + '''        if opaqueBackdrop {
            ctx.setFillColor(UIColor.systemBackground.resolvedColor(with: sourceView.traitCollection).cgColor)
            ctx.fill(''' + rect + ''')
        }
''')


def compensation(s):
    return replace(s, '                glass.backgroundColor = glass.captureVeilColor', '''                let layer = CALayer()
                layer.frame = glass.bounds.insetBy(dx: glass.shape.widthInset, dy: glass.shape.heightInset)
                layer.cornerRadius = min(glass.shape.cornerRadius, min(layer.bounds.width, layer.bounds.height) / 2)
                layer.backgroundColor = glass.captureVeilColor.cgColor
                glass.layer.insertSublayer(layer, above: host.layer)
                entry.snapshotLayer = layer''')


def tab_frame_policy(s):
    s = replace(s, '    var ngHostIsInteracting: Bool { isDragging || isCollapsingLens }', '''    var ngHostIsInteracting: Bool { isDragging || isCollapsingLens }

    private func ngInvalidatePageFrames(selectionDelay: TimeInterval = 0) {
        backgroundGlassView.ngInvalidateBackdrop(after: 0)
        selectionView.ngInvalidateBackdrop(after: selectionDelay)
        if let lens = theseusView, !lens.isHidden {
            // Keep the original growing/shrinking lens; refresh its input on release.
            lens.invalidateBackground()
        }
    }''')
    s = replace(s, '        if isCollapsingLens { endDragImmediately() }\n        selectedIndex = index', '''        if isDragging || isCollapsingLens {
            let shown = theseusView.flatMap { $0.isHidden ? nil : ngVisibleLensFrame($0) }
            endDragImmediately()
            if let shown {
                let center = convertFromTheseusContainer(shown).midX
                UIView.performWithoutAnimation { selectionView.center.x = center }
            }
        }
        ngInvalidatePageFrames(selectionDelay: TheseusSettings.shared.areMorphAnimationsEnabled ? 0.22 : 0)
        selectedIndex = index''')
    s = replace(s, '            if isCollapsingLens, confirmed != selectedIndex { endDragImmediately() }\n            selectedIndex = confirmed', '            ngApplySelection(confirmed)')
    s = replace(s, '        let frame = selectionFrame(for: slotFrame(at: selectedIndex))', '''        let rawFrame = selectionFrame(for: slotFrame(at: selectedIndex))
        let frame: CGRect
        if ngUseHostPosition, window != nil {
            let scale = traitCollection.displayScale > 0 ? traitCollection.displayScale : UIScreen.main.scale
            let screenFrame = contentView.convert(rawFrame, to: nil)
            frame = contentView.convert(NGTabPresentation.pixelAligned(screenFrame, scale: scale), from: nil)
        } else {
            frame = rawFrame
        }''')
    s = replace(s, '        if selectionView.shape.cornerRadius != frame.height / 2 {\n            selectionView.shape.cornerRadius = frame.height / 2', '''        let radius = ngUseHostPosition ? min(frame.width, frame.height) / 2 : frame.height / 2
        if ngUseHostPosition {
            selectionView.layer.cornerCurve = .continuous
            selectionView.layer.masksToBounds = true
        }
        if selectionView.shape.cornerRadius != radius {
            selectionView.shape.cornerRadius = radius''')
    s = replace(s, '            pillShadeLayer.cornerRadius = size.height / 2',
                '            pillShadeLayer.cornerRadius = (ngUseHostPosition ? min(size.width, size.height) : size.height) / 2')
    s = replace(s, '        selectionView.shape.cornerRadius = pillLocal.height / 2',
                '        selectionView.shape.cornerRadius = (ngUseHostPosition ? min(pillLocal.width, pillLocal.height) : pillLocal.height) / 2')
    return replace(s, '                    isCommittingDrag = true\n                    selectedIndex = confirmed', '''                    if confirmed != selectedIndex { ngInvalidatePageFrames() }
                    isCommittingDrag = true
                    selectedIndex = confirmed''')


def renderer_frame_policy(s):
    # Preserve the upstream frame rate, resolution and render scheduling. Only the
    # adapter's static surfaces defer capture to the next run-loop opportunity.
    s = replace(s, '    var continuousUpdate: Bool = false {', '''    var ngCaptureNotBefore: CFTimeInterval = 0

    var continuousUpdate: Bool = false {''')
    s = replace(s, '        guard shouldRender() else { return }',
                '        guard CACurrentMediaTime() >= ngCaptureNotBefore, shouldRender() else { return }')
    return replace(s, '        commandBuffer.addCompletedHandler { [weak self] _ in\n            guard let image = Self.image(from: snapshot) else { return }\n            DispatchQueue.main.async { self?.onSnapshot?(image) }', '''        let onSnapshot = self.onSnapshot
        commandBuffer.addCompletedHandler { buffer in
            guard buffer.status == .completed, let image = Self.image(from: snapshot) else { return }
            DispatchQueue.main.async { onSnapshot?(image) }''')


def surface_frame_policy(s):
    s = replace(s, '    private var ngPresented = false', '''    private var ngPresented = false
    private var ngBackdropEpoch: UInt64 = 0
    private var ngCaptureNotBefore: CFTimeInterval = 0
    var ngSelectionBackdrop = false
    private var ngSwitchCover: UIView?

    // An opaque, detail-free fill sampled from the last settled surface, not
    // the old page image. Keep it below the existing rim and pill shading.
    private func ngShowSwitchCover(over metal: UIView) {
        let dark = traitCollection.userInterfaceStyle == .dark
        let neutral: CGFloat = ngSelectionBackdrop ? (dark ? 0.26 : 0.88) : (dark ? 0.18 : 0.96)
        let cover = ngSwitchCover ?? UIView(frame: bounds)
        if ngSwitchCover == nil {
            cover.isUserInteractionEnabled = false
            cover.isAccessibilityElement = false
            cover.clipsToBounds = true
            insertSubview(cover, aboveSubview: metal)
            ngSwitchCover = cover
        }
        let fill = renderedCenterColor ?? cover.backgroundColor ?? UIColor(white: neutral, alpha: 1)
        UIView.performWithoutAnimation {
            cover.layer.removeAllAnimations()
            cover.frame = bounds
            cover.layer.cornerRadius = shape.cornerRadius
            cover.backgroundColor = fill
            cover.isHidden = false
            cover.alpha = 1
            fallbackView?.isHidden = true
            metal.alpha = 0
        }
    }

    func ngInvalidateBackdrop(after delay: TimeInterval) {
        ngBackdropEpoch &+= 1
        let metal = metalLayerView
        let useSwitchCover = ngOpaqueBackdrop && !isUsingFallback && renderer != nil && metal != nil
        if useSwitchCover, let metal { ngShowSwitchCover(over: metal) }
        ngCaptureNotBefore = CACurrentMediaTime() + delay
        ngPresented = false
        captureSnapshot = nil
        captureSnapshotOverride = nil
        if useSwitchCover {
            ngWaitingForPresent = true
            ngConfigurePresentCallback()
        } else {
            ngSwitchCover?.isHidden = true
            ngPrepareReplacement()
        }
        renderer?.ngCaptureNotBefore = ngCaptureNotBefore
        applySnapshotSetting()
        renderer?.setNeedsRender()
    }''')
    s = replace(s, '        fallbackView?.isHidden = false\n        ngConfigurePresentCallback()', '''        fallbackView?.isHidden = false
        // Keep acquiring drawables while masking the stale texture on screen.
        if ngOpaqueBackdrop { metalLayerView?.alpha = 0 }
        ngConfigurePresentCallback()''')
    s = replace(s, '            renderer?.onPresent = { [weak self] in self?.ngFramePresented() }', '''            let epoch = ngBackdropEpoch
            renderer?.onPresent = { [weak self] in
                guard let self, self.ngBackdropEpoch == epoch, !self.isUsingFallback else { return }
                self.ngFramePresented()
            }''')
    s = replace(s, '        if !isUsingFallback { fallbackView?.isHidden = true }', '''        if !isUsingFallback {
            UIView.performWithoutAnimation {
                metalLayerView?.alpha = 1
                fallbackView?.isHidden = true
            }
            if let cover = ngSwitchCover, !cover.isHidden, cover.alpha > 0 {
                let epoch = ngBackdropEpoch
                UIView.animate(withDuration: 0.08, delay: 0, options: [.allowUserInteraction, .curveEaseOut]) {
                    cover.alpha = 0
                } completion: { [weak self, weak cover] finished in
                    guard finished, let self, self.ngBackdropEpoch == epoch else { return }
                    cover?.isHidden = true
                }
            }
        }''')
    s = replace(s, '        fallbackView?.frame = bounds\n\n        guard let metalLayer', '''        fallbackView?.frame = bounds
        if let cover = ngSwitchCover {
            cover.frame = bounds
            cover.layer.cornerRadius = shape.cornerRadius
        }

        guard let metalLayer''')
    s = replace(s, '            renderer = nil\n            metalLayerView?.isHidden = true', '''            renderer = nil
            ngSwitchCover?.layer.removeAllAnimations()
            ngSwitchCover?.isHidden = true
            metalLayerView?.isHidden = true''')
    s = replace(s, '        renderer?.onSnapshot = providesCaptureSnapshot ? { [weak self] image in\n            self?.captureSnapshot = image\n            self?.snapshotDidUpdate?()', '''        let epoch = ngBackdropEpoch
        renderer?.onSnapshot = providesCaptureSnapshot ? { [weak self] image in
            guard let self, self.ngBackdropEpoch == epoch else { return }
            self.captureSnapshot = image
            self.snapshotDidUpdate?()''')
    s = replace(s, '        renderer?.hostView = self\n        renderer?.configuration', '''        renderer?.hostView = self
        renderer?.ngCaptureNotBefore = ngCaptureNotBefore
        renderer?.configuration''')
    return s


def motion_policy(s):
    s = replace(s, '    var ngActivateNative: ((Int) -> Int?)?', '''    private var ngGestureGate = NGTabInteractionGate()
    private weak var ngPressGesture: UILongPressGestureRecognizer?
    private lazy var ngTap = UITapGestureRecognizer(target: self, action: #selector(ngTapped(_:)))

    private func ngAcceptGesture(_ gesture: UIGestureRecognizer) -> Bool {
        let owner = ObjectIdentifier(gesture)
        switch gesture.state {
        case .began:
            guard !isDragging, isUserInteractionEnabled, slotFrames.indices.contains(selectedIndex) else { return false }
            let index = findClosestItemIndex(to: gesture.location(in: contentView))
            guard items.indices.contains(index), items[index].ngEnabled else { return false }
            return ngGestureGate.begin(owner)
        case .changed: return ngGestureGate.accepts(owner)
        case .ended, .cancelled, .failed: return ngGestureGate.end(owner)
        default: return false
        }
    }

    @objc private func ngTapped(_ gesture: UITapGestureRecognizer) {
        guard gesture.state == .ended, !isDragging, !slotFrames.isEmpty else { return }
        selectItem(at: findClosestItemIndex(to: gesture.location(in: contentView)))
    }

    private func ngLensShapeFrame(_ glass: TheseusView, frame: CGRect, bounds: CGRect) -> CGRect? {
        NGTabPresentation.visibleLens(frame: frame, bounds: bounds,
                                      inset: CGSize(width: glass.shape.widthInset, height: glass.shape.heightInset))
    }

    private func ngVisibleLensFrame(_ glass: TheseusView) -> CGRect? {
        if let live = glass.layer.presentation(),
           let frame = ngLensShapeFrame(glass, frame: live.frame, bounds: live.bounds) { return frame }
        return ngLensShapeFrame(glass, frame: glass.layer.frame, bounds: glass.layer.bounds)
    }

    var ngActivateNative: ((Int) -> Int?)?''')
    s = replace(s, '            backgroundGlassView.ngOpaqueBackdrop = ngUseHostPosition', '''            ngTap.isEnabled = ngUseHostPosition
            backgroundGlassView.ngFrostedPlatter = ngUseHostPosition
            var chrome = backgroundGlassView.configuration
            chrome.blur.radius = ngUseHostPosition ? 26 : 18
            chrome.blur.sigma = ngUseHostPosition ? 9 : nil
            chrome.refraction.interiorSharpness = ngUseHostPosition ? 0 : Self.chromeDetailLight
            backgroundGlassView.configuration = chrome
            backgroundGlassView.ngOpaqueBackdrop = ngUseHostPosition''')
    s = replace(s, '        pressGesture.minimumPressDuration = 0', '        pressGesture.minimumPressDuration = ngUseHostPosition ? 0.15 : 0\n        ngPressGesture = pressGesture')
    s = replace(s, '        addGestureRecognizer(panGesture)', '''        addGestureRecognizer(panGesture)
        ngTap.isEnabled = ngUseHostPosition
        ngTap.delegate = self
        ngTap.require(toFail: pressGesture)
        ngTap.require(toFail: panGesture)
        addGestureRecognizer(ngTap)''')
    # ngUseHostPosition is set after init; set the existing press recognizer then.
    s = replace(s, '            ngTap.isEnabled = ngUseHostPosition', '''            ngTap.isEnabled = ngUseHostPosition
            ngPressGesture?.minimumPressDuration = ngUseHostPosition ? 0.15 : 0
            ngPressGesture?.allowableMovement = ngUseHostPosition ? 10 : .greatestFiniteMagnitude''')
    s = replace(s, '    @objc private func handlePress(_ gesture: TouchTimestampingPressGestureRecognizer) {', '''    @objc private func handlePress(_ gesture: TouchTimestampingPressGestureRecognizer) {
        if ngUseHostPosition && !ngAcceptGesture(gesture) { return }''')
    s = replace(s, '    @objc private func handlePan(_ gesture: UIPanGestureRecognizer) {', '''    @objc private func handlePan(_ gesture: UIPanGestureRecognizer) {
        if ngUseHostPosition && !ngAcceptGesture(gesture) { return }''')
    s = replace(s, '        guard let pan = gestureRecognizer as? UIPanGestureRecognizer,', '''        if ngUseHostPosition {
            if gestureRecognizer === ngTap { return !isDragging && !slotFrames.isEmpty }
            if let pan = gestureRecognizer as? UIPanGestureRecognizer, pan.view === self {
                let velocity = pan.velocity(in: self)
                return !slotFrames.isEmpty && abs(velocity.x) > abs(velocity.y)
            }
        }
        guard let pan = gestureRecognizer as? UIPanGestureRecognizer,''')
    s = replace(s, '        gestureRecognizer.view === self && otherGestureRecognizer.view === self',
                '        !ngUseHostPosition && gestureRecognizer.view === self && otherGestureRecognizer.view === self')
    s = replace(s, '        layoutItemViews()\n        updateSelectionViewFrame(animated: false)', '''        layoutItemViews()
        // A native relayout cannot reset a pill currently mapped onto the lens.
        if !ngUseHostPosition || (!isDragging && !isCollapsingLens && lensMorphAnimator?.isRunning != true) {
            updateSelectionViewFrame(animated: false)
        }''')
    s = replace(s, '        backgroundGlassView.configuration.refraction.interiorSharpness = isDark ? Self.chromeDetailDark : Self.chromeDetailLight',
                '        backgroundGlassView.configuration.refraction.interiorSharpness = ngUseHostPosition ? 0 : (isDark ? Self.chromeDetailDark : Self.chromeDetailLight)')
    a = s.index('    private func applyBarBodyGain(')
    b = s.index('    private func startFlexSpread(', a)
    gain = s[a:b]
    gain = replace(gain, '        backgroundView.backgroundColor = .clear\n',
                   '        backgroundView.backgroundColor = .clear\n        var config = backgroundGlassView.configuration\n')
    gain = replace(gain, '        backgroundGlassView.invalidateBackground()', '        backgroundGlassView.configuration = config')
    gain = gain.replace('backgroundGlassView.configuration.', 'config.')
    s = s[:a] + gain + s[b:]
    s = replace(s, '        if let sourceView = theseusSourceView, sourceView.bounds.width > 0 {',
                '        if let sourceView = theseusSourceView, sourceView.bounds.width > 0, glassView.sourceView !== sourceView {')
    s = replace(s, '''        let startFrame: CGRect
        let startProgress: CGFloat
        if glassView.isHidden {
            startFrame = pillFrame
            startProgress = 0
        } else {
            startFrame = glassView.frame
            startProgress = lensItemProgress
        }''', '''        let startFrame: CGRect
        let startProgress: CGFloat
        if glassView.isHidden {
            let visiblePill = selectionView.layer.presentation()?.frame ?? selectionView.layer.frame
            startFrame = ngUseHostPosition && !visiblePill.isEmpty
                ? convertToTheseusContainer(visiblePill) : pillFrame
            startProgress = 0
        } else {
            startFrame = (ngUseHostPosition ? ngVisibleLensFrame(glassView) : nil) ?? glassView.frame
            startProgress = lensItemProgress
        }''')
    s = replace(s, '        glassView.layer.transform = LensMorph.transform(mapping: hostFrame, onto: startFrame)', '''        let morphBase = ngUseHostPosition
            ? hostFrame.insetBy(dx: lensShape.widthInset, dy: lensShape.heightInset) : hostFrame
        let growthTarget = ngUseHostPosition ? lensFrame.insetBy(dx: -lensOutset, dy: -lensOutset) : lensFrame
        glassView.layer.transform = LensMorph.transform(mapping: morphBase, onto: startFrame)''')
    s = replace(s, 'animator.morph(from: startFrame, to: lensFrame, spring: Self.lensGrowSpring',
                'animator.morph(from: startFrame, to: growthTarget, spring: Self.lensGrowSpring')
    # Sample the visible pose BEFORE cancelling transforms. Continue to use
    # the same drawable and model shape for the entire hosted shrink.
    s = replace(s, '        selectionAnimator?.cancel()\n        lensMorphAnimator?.cancel()\n        stopLensStretch()\n\n        setBarLifted(false)', '''        let shown = ngUseHostPosition ? ngVisibleLensFrame(glassView) : nil
        selectionAnimator?.cancel()
        lensMorphAnimator?.cancel()
        stopLensStretch()

        setBarLifted(false)''')
    s = replace(s, '''        selectionView.isHidden = false
        fadePill(to: 1, spring: Self.pillFadeInSpring)
        glassView.layer.transform = CATransform3DIdentity
        let releaseFrame = glassView.frame.insetBy(dx: glassView.shape.widthInset, dy: glassView.shape.heightInset)
        if glassView.shape.widthInset != 0 || glassView.shape.heightInset != 0 {
            glassView.frame = releaseFrame
            var shape = glassView.shape
            shape.widthInset = 0
            shape.heightInset = 0
            shape.cornerRadius = lensCornerRadius(forHeight: releaseFrame.height)
            glassView.shape = shape
        }''', '''        if ngUseHostPosition {
            pillFadeDriver.stop()
            isPillFading = false
            selectionView.isHidden = false
            selectionView.alpha = 0
        } else {
            selectionView.isHidden = false
            fadePill(to: 1, spring: Self.pillFadeInSpring)
        }
        let size = glassView.bounds.size
        let modelFrame = CGRect(x: glassView.center.x - size.width / 2, y: glassView.center.y - size.height / 2,
                                width: size.width, height: size.height)
        let releaseFrame: CGRect
        let animationBase: CGRect
        if let shown, let base = ngLensShapeFrame(glassView, frame: modelFrame, bounds: glassView.bounds) {
            releaseFrame = shown
            animationBase = base
        } else {
            glassView.layer.transform = CATransform3DIdentity
            releaseFrame = glassView.frame.insetBy(dx: glassView.shape.widthInset, dy: glassView.shape.heightInset)
            animationBase = releaseFrame
            if glassView.shape.widthInset != 0 || glassView.shape.heightInset != 0 {
                glassView.frame = releaseFrame
                var shape = glassView.shape
                shape.widthInset = 0
                shape.heightInset = 0
                shape.cornerRadius = lensCornerRadius(forHeight: releaseFrame.height)
                glassView.shape = shape
            }
        }
        guard !releaseFrame.isEmpty, !animationBase.isEmpty else { endDragImmediately(); return }''')
    s = replace(s, '            glassView.layer.transform = LensMorph.transform(mapping: releaseFrame, onto: frame)', '''            glassView.layer.transform = LensMorph.transform(mapping: animationBase, onto: frame)
            if self.ngUseHostPosition {
                let pill = self.convertFromTheseusContainer(frame)
                self.selectionView.bounds = CGRect(origin: .zero, size: pill.size)
                self.selectionView.center = CGPoint(x: pill.midX, y: pill.midY)
                self.selectionView.shape.cornerRadius = pill.height / 2
                let capsuleShare = min(max(progress, 0), 1)
                self.selectionView.alpha = capsuleShare
                glassView.alpha = 1 - capsuleShare
            }''')
    s = replace(s, '            self.isCollapsingLens = false\n            self.selectionView.isHidden = false', '''            self.isCollapsingLens = false
            if self.ngUseHostPosition {
                self.updateSelectionViewFrame(animated: false)
                self.selectionView.alpha = 1
                self.selectionView.isHidden = false
            }
            self.selectionView.isHidden = false''')
    s = replace(s, '    private func endDragImmediately() {\n        isDragging = false',
                '    private func endDragImmediately() {\n        ngGestureGate.clear()\n        isDragging = false')
    s = replace(s, '        isDragging = false\n        resetFlexGlow()\n        bodyGainDriver.stop()', '        isDragging = false\n        ngGestureGate.clear()\n        resetFlexGlow()\n        bodyGainDriver.stop()')
    s = replace(s, '            currentDragVelocity = gesture.velocity(in: self)\n', '''            currentDragVelocity = gesture.velocity(in: self)
            if ngUseHostPosition { followFinger(at: gesture.location(in: self)) }
''')
    # Let the touch spring own the center while the grow morph owns size.
    # Otherwise the grow spring keeps filtering the moving spring target.
    s = replace(s, '    private var ngGestureGate = NGTabInteractionGate()',
                '    private var ngGestureGate = NGTabInteractionGate()\n    private var ngFollowFrame: CGRect?')
    s = replace(s, '        isDragging = true\n        let anchorX', '        isDragging = true\n        ngFollowFrame = nil\n        let anchorX')
    s = replace(s, '        let shown = ngUseHostPosition ? ngVisibleLensFrame(glassView) : nil\n        selectionAnimator?.cancel()',
                '        let shown = ngUseHostPosition ? ngVisibleLensFrame(glassView) : nil\n        ngFollowFrame = nil\n        selectionAnimator?.cancel()')
    s = replace(s, '                    morph.retarget(to: containerFrame)', '''                    if self.ngUseHostPosition { self.ngFollowFrame = frame }
                    else { morph.retarget(to: containerFrame) }''')
    s = replace(s, '            lastFrame = frame\n            glassView.layer.transform = self.stretched', '''            var placed = frame
            if let follow = self.ngFollowFrame {
                let target = self.convertToTheseusContainer(follow)
                placed = frame.offsetBy(dx: target.midX - frame.midX, dy: target.midY - frame.midY)
            }
            lastFrame = placed
            glassView.layer.transform = self.stretched''')
    s = replace(s, 'LensMorph.transform(mapping: hostFrame, onto: frame))\n            let localFrame = self.convertFromTheseusContainer(frame)',
                'LensMorph.transform(mapping: morphBase, onto: placed))\n            let localFrame = self.convertFromTheseusContainer(placed)')
    s = replace(s, '            glassView.layer.transform = self.stretched(CATransform3DIdentity)\n            self.placeLens(at: lastFrame)', '''            self.ngFollowFrame = nil
            glassView.layer.transform = self.stretched(CATransform3DIdentity)
            // placeLens adds the rim outset itself; lastFrame already includes it.
            let body = self.ngUseHostPosition ? lastFrame.insetBy(dx: self.lensOutset, dy: self.lensOutset) : lastFrame
            self.placeLens(at: body)''')
    s = replace(s, '        selectionAnimator?.rest(at: restingCenterX)',
                '        selectionAnimator?.rest(at: restingCenterX, immediate: ngUseHostPosition)')
    s = replace(s, '    private var flyStart: CFTimeInterval = 0',
                '    private var flyStart: CFTimeInterval = 0\n    private var flyWait: CFTimeInterval = SelectionAnimator.flyDelay')
    s = replace(s, 'flyStart = time + Self.flyDelay', 'flyStart = time + flyWait')
    s = replace(s, '    func rest(at x: CGFloat) {\n        cancel()',
                '    func rest(at x: CGFloat, immediate: Bool = false) {\n        cancel()\n        flyWait = immediate ? 0 : Self.flyDelay')
    s = replace(s, '                self.setupTheseus()\n                self.theseusView?.pauseRendering()', '''                guard !self.isDragging, !self.isCollapsingLens else { return }
                self.setupTheseus()
                self.theseusView?.pauseRendering()''')
    return s


def nonblocking_lens_renderer(s):
    s = replace(s, '    var ngCaptureNotBefore: CFTimeInterval = 0',
                '    var ngCaptureNotBefore: CFTimeInterval = 0\n    var ngNonblockingRendering = false\n    var ngCaptureScale: CGFloat = 1')
    s = replace(s, '        let renderScale = currentRefractionQuality.renderScale',
                '        let renderScale = currentRefractionQuality.renderScale * ngCaptureScale')
    s = replace(s, 'metalLayer?.presentsWithTransaction = continuousUpdate',
                'metalLayer?.presentsWithTransaction = continuousUpdate && !ngNonblockingRendering')
    s = replace(s, '        isRendering = true\n        markAllFramesCompleted()', '''        isRendering = true
        // Reopening the lens does not make pre-pause work complete.
        if !ngNonblockingRendering { markAllFramesCompleted() }''')
    s = replace(s, '        waitForGPUCompletion()\n        markAllFramesCompleted()', '''        if !ngNonblockingRendering {
            waitForGPUCompletion()
            markAllFramesCompleted()
        }''')
    s = replace(s, 'set { frameCounterLock.withLock { _lastCompletedFrame = newValue } }',
                'set { frameCounterLock.withLock { _lastCompletedFrame = max(_lastCompletedFrame, newValue) } }')
    s = replace(s, '        guard framesInFlight < Self.maxFramesInFlight else { return }',
                '        guard framesInFlight < (ngNonblockingRendering ? 2 : Self.maxFramesInFlight) else { return }')
    s = replace(s, '        commandBuffer.encodeSignalEvent(frameEvent, value: frameValue)',
                '        if !ngNonblockingRendering { commandBuffer.encodeSignalEvent(frameEvent, value: frameValue) }')
    a = s.index('        frameEvent.notify(')
    b = s.index('        commandBuffer.commit()', a)
    s = s[:a]+'''        // Only pools and immutable per-frame references cross onto the completion queue.
        let pool = texturePool
        let surfaceCapture = viewLayerCapture
        let surface = capturedSurface
        let extra = frostTextures?.pooled ?? []
        let recycle = { [weak self] in
            pool.checkin(intermediateTexture1)
            pool.checkin(intermediateTexture2)
            for texture in extra { pool.checkin(texture) }
            if let surface { surfaceCapture?.recycleSurface(surface) }
            self?.lastCompletedFrame = frameValue
        }
        if ngNonblockingRendering {
            // Completion also releases the slot when the GPU drops or fails a frame.
            commandBuffer.addCompletedHandler { _ in recycle() }
        } else {
            frameEvent.notify(context.eventListener, atValue: frameValue) { _, _ in recycle() }
        }

'''+s[b:]
    return s


def motion_surface(s):
    s = replace(s, '    var ngSelectionBackdrop = false', '''    var ngSelectionBackdrop = false
    var ngNonblockingRendering = false
    var ngCaptureScale: CGFloat = 1 { didSet { renderer?.ngCaptureScale = ngCaptureScale } }
    var ngFrostedPlatter = false''')
    s = replace(s, '        renderer?.hostView = self\n        renderer?.ngCaptureNotBefore = ngCaptureNotBefore\n        renderer?.configuration = configuration', '''        renderer?.hostView = self
        renderer?.ngCaptureNotBefore = ngCaptureNotBefore
        renderer?.ngNonblockingRendering = ngNonblockingRendering
        renderer?.configuration = configuration''')
    s = replace(s, '            fallbackView?.configure(with: configuration)\n            if oldValue.shape', '''            // The retained fallback is normally hidden. A drag should not
            // rebuild its gradients and blur bookkeeping on each frame.
            if let fallbackView, !fallbackView.isHidden { fallbackView.configure(with: configuration) }
            if oldValue.shape''')
    s = replace(s, '        fallbackView?.configure(with: configuration)\n        fallbackView?.updateForTraitCollection(traitCollection)',
                '        fallbackView?.ngFrostedPlatter = ngFrostedPlatter\n        fallbackView?.configure(with: configuration)\n        fallbackView?.updateForTraitCollection(traitCollection)')
    return replace(s, '            fallbackView?.isHidden = false\n            fallbackView?.configure(with: configuration)',
                   '            fallbackView?.isHidden = false\n            fallbackView?.ngFrostedPlatter = ngFrostedPlatter\n            fallbackView?.configure(with: configuration)')


def frosted_platter_fallback(s):
    s = replace(s, '    private var lastConfiguration: TheseusConfiguration?',
                '    var ngFrostedPlatter = false\n\n    private var lastConfiguration: TheseusConfiguration?')
    return replace(s, '        blurView.effect = UIBlurEffect(style: Self.thinBlurStyle(isDark: isDark))', '''        let style: UIBlurEffect.Style = ngFrostedPlatter ? (isDark ? .systemMaterialDark : .systemMaterialLight)
            : Self.thinBlurStyle(isDark: isDark)
        blurView.alpha = ngFrostedPlatter ? 1 : 0.7
        blurView.effect = UIBlurEffect(style: style)''')


def opaque_selection_tab(s):
    s = replace(s, '''            selectionView.ngOpaqueBackdrop = ngUseHostPosition
            selectionView.ngSelectionBackdrop = ngUseHostPosition''',
                '            if ngUseHostPosition { selectionView.ngEnableSolidSelection() }')
    s = replace(s, '        selectionView.ngPrepareReplacement()',
                '        if !ngUseHostPosition { selectionView.ngPrepareReplacement() }')
    s = replace(s, '''    private func ngInvalidatePageFrames(selectionDelay: TimeInterval = 0) {
        backgroundGlassView.ngInvalidateBackdrop(after: 0)
        selectionView.ngInvalidateBackdrop(after: selectionDelay)''', '''    private func ngInvalidatePageFrames() {
        backgroundGlassView.ngInvalidateBackdrop(after: 0)''')
    s = replace(s, 'ngInvalidatePageFrames(selectionDelay: TheseusSettings.shared.areMorphAnimationsEnabled ? 0.22 : 0)',
                'ngInvalidatePageFrames()')
    s = replace(s, '            selectionView.sourceView = source',
                '            if !ngUseHostPosition { selectionView.sourceView = source }')
    return replace(s, '                if self.selectionView.sourceView == nil {',
                   '                if !self.ngUseHostPosition, self.selectionView.sourceView == nil {')


def opaque_selection_surface(s):
    s = replace(s, '    var ngSelectionBackdrop = false', '''    private var ngSolidSelection = false

    // Hosted selection is an opaque tint, not another capture of the page.
    // Keep this same view so the pill geometry and motion do not change.
    func ngEnableSolidSelection() {
        guard !ngSolidSelection else { return }
        ngSolidSelection = true
        ngBackdropEpoch &+= 1
        ngWaitingForPresent = false
        renderer?.stopRendering()
        renderer = nil
        providesCaptureSnapshot = false
        captureSnapshotOverride = nil
        sourceView = nil
        fallbackView?.isHidden = true
        ngSwitchCover?.isHidden = true
        metalLayerView?.isHidden = true
        ngUpdateSolidSelection()
    }

    private func ngUpdateSolidSelection() {
        let tone: CGFloat = traitCollection.userInterfaceStyle == .dark ? 0.26 : 0.88
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        backgroundColor = UIColor(white: tone, alpha: 1)
        layer.cornerRadius = shape.cornerRadius
        CATransaction.commit()
    }
'''.rstrip('\n'))
    s = replace(s, 'let neutral: CGFloat = ngSelectionBackdrop ? (dark ? 0.26 : 0.88) : (dark ? 0.18 : 0.96)',
                'let neutral: CGFloat = dark ? 0.18 : 0.96')
    s = replace(s, '        didSet {\n            renderer?.updateConfiguration(configuration)',
                '        didSet {\n            if ngSolidSelection { ngUpdateSolidSelection(); return }\n            renderer?.updateConfiguration(configuration)')
    s = replace(s, '    var renderedCenterColor: UIColor? {\n        guard let snapshot',
                '    var renderedCenterColor: UIColor? {\n        if ngSolidSelection { return backgroundColor }\n        guard let snapshot')
    # Let lens captures draw the solid fill normally; never substitute a live page image.
    s = replace(s, 'var captureMetalHost: UIView? { metalLayerView }',
                'var captureMetalHost: UIView? { ngSolidSelection ? nil : metalLayerView }')
    for signature in ('func ngInvalidateBackdrop(after delay: TimeInterval)',
                      'func ngPrepareReplacement()', 'private func setupRenderer()',
                      'private func updateRenderingMode()'):
        line = '    ' + signature + ' {\n'
        s = replace(s, line, line + '        guard !ngSolidSelection else { return }\n')
    return replace(s, '        super.traitCollectionDidChange(previousTraitCollection)\n        fallbackView?',
                   '        super.traitCollectionDidChange(previousTraitCollection)\n        if ngSolidSelection { ngUpdateSolidSelection(); return }\n        fallbackView?')


def stage(dst):
    verify_vendor()
    def adapted_tab(s):
        s = opaque_selection_tab(motion_policy(tab_frame_policy(tabbar(s))))
        s = stability.appearance_tab(stability.drag_tab(s, replace), replace)
        s = hosted_appearance.tab(hosted_motion.tab(s, replace), replace)
        s = hosted_compositor.tab(s, replace)
        return platter_edges.tab(s, replace)

    def adapted_renderer(s):
        s = nonblocking_lens_renderer(renderer_frame_policy(renderer(s)))
        s = stability.appearance_renderer(stability.drag_renderer(s, replace), replace)
        return hosted_appearance.renderer(hosted_motion.renderer(s, replace), replace)

    def adapted_surface(s):
        s = opaque_selection_surface(motion_surface(surface_frame_policy(surface(s))))
        s = stability.appearance_surface(s, replace)
        return hosted_appearance.surface(hosted_motion.surface(s, replace), replace)

    def adapted_capture(s, rect):
        return stability.bounded_capture(opaque_capture(s, rect), replace)

    patches = {'TheseusTabBar.swift':adapted_tab,
               'TheseusRenderer.swift':adapted_renderer,
               'TheseusView.swift':adapted_surface,
               'VisualEffectFallback.swift':frosted_platter_fallback,
               'CaptureCompensation.swift':lambda s: stability.bounded_compensation(compensation(s), replace),
               'BackgroundCaptureDraw.swift':lambda s: adapted_capture(s, 'CGRect(x: 0, y: 0, width: width, height: height)'),
               'ViewLayerCapture.swift':lambda s: adapted_capture(s, 'CGRect(x: 0, y: 0, width: pixelWidth, height: pixelHeight)')}
    dst.mkdir(parents=True,exist_ok=True)
    for p in sorted((VENDOR/'Sources/Theseus').rglob('*.swift')):
        s = p.read_text()
        if p.name in patches:
            s = patches[p.name](s)
        (dst/p.name).write_text(s)
    if len(list(dst.glob('*.swift'))) != 33:
        raise SystemExit('Unexpected Swift source count')


if __name__ == '__main__':
    stage(Path(sys.argv[1]))

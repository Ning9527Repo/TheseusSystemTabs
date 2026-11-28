import UIKit
import QuartzCore

private struct WeChatTabData: Equatable {
    let identity: ObjectIdentifier
    let title: String
    let image: UIImage?
    let selectedImage: UIImage?
    let badge: String?
    let label: String?
    let enabled: Bool
    let redDot: Bool

    init(_ entry: NGWeChatTabEntry) {
        identity = ObjectIdentifier(entry.identity as AnyObject)
        title = entry.title ?? ""
        image = entry.image
        selectedImage = entry.selectedImage
        badge = entry.badge
        label = entry.label
        enabled = entry.enabled
        redDot = entry.redDot
    }

    func makeItem() -> TheseusTabBarItem {
        var item = TheseusTabBarItem(icon: image, selectedIcon: selectedImage, title: title)
        item.ngBadge = badge
        item.ngBadgeColor = .systemRed
        item.ngLabel = label ?? title
        item.ngEnabled = enabled
        return item
    }
}

@MainActor private final class WeChatTabsState {
    weak var native: UIView?
    let glass = TheseusTabBar(frame: .zero)
    let nativeMask = CALayer()
    let originalMask: CALayer?
    private var timer: Timer?
    private var data: [WeChatTabData] = []
    private var dots: [UIView] = []
    private var activationPending = false
    private var stopped = false
    private(set) var presented = false
    private(set) var sourceFrame = CGRect.zero

    init(_ bar: UIView) {
        native = bar
        originalMask = bar.layer.mask
        nativeMask.backgroundColor = UIColor.clear.cgColor
        glass.barHeight = 63
        glass.ngUseHostPosition = true
        glass.ngExcludedBar = bar
        glass.ngActivateNative = { [weak self] index in self?.activate(index) }
        for _ in 0..<4 {
            let dot = UIView()
            dot.backgroundColor = .systemRed
            dot.isUserInteractionEnabled = false
            dot.isAccessibilityElement = false
            dot.layer.cornerRadius = 3
            dot.isHidden = true
            glass.addSubview(dot)
            dots.append(dot)
        }
    }

    deinit { timer?.invalidate() }

    func attach(_ bar: UIView, parent: UIView, frame: CGRect) {
        sourceFrame = frame
        glass.ngApplyHostFrame(frame)
        parent.insertSubview(glass, aboveSubview: bar)
        timer = Timer(timeInterval: 1.0 / 12, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self, let bar = self.native, !self.stopped else { return }
                WeChatTabsBridge.update(bar)
            }
        }
        timer?.tolerance = 0.02
        if let timer { RunLoop.main.add(timer, forMode: .common) }
    }

    func apply(_ snapshot: NGWeChatTabSnapshot, bar: UIView, parent: UIView, frame: CGRect) {
        guard !stopped else { return }
        if glass.superview !== parent { glass.removeFromSuperview(); parent.insertSubview(glass, aboveSubview: bar) }
        // Navigation transitions can reorder native siblings; keep the same overlay above its source.
        if let nativeIndex = parent.subviews.firstIndex(where: { $0 === bar }),
           let glassIndex = parent.subviews.firstIndex(where: { $0 === glass }), glassIndex <= nativeIndex {
            parent.insertSubview(glass, aboveSubview: bar)
        }
        if glass.overrideUserInterfaceStyle != bar.overrideUserInterfaceStyle {
            glass.overrideUserInterfaceStyle = bar.overrideUserInterfaceStyle
        }
        if !glass.ngHostIsInteracting && sourceFrame != frame {
            sourceFrame = frame
            glass.ngApplyHostFrame(frame)
        }
        if !glass.ngHostIsInteracting && !activationPending {
            let next = snapshot.entries.map { WeChatTabData($0) }
            if data != next {
                if data.map(\.identity) == next.map(\.identity) {
                    glass.ngRefreshItems(next.map { $0.makeItem() }, changed: next.indices.filter { next[$0] != data[$0] })
                } else {
                    glass.items = next.map { $0.makeItem() }
                }
                data = next
            }
            let selected = Int(snapshot.selectedIndex)
            let selectedColor = snapshot.entries[selected].selectedColor ?? bar.tintColor ?? .systemGreen
            let normalColor = snapshot.entries[selected].normalColor ?? TheseusTabBar.nativeUnselectedTint
            if glass.selectedTintColor != selectedColor { glass.selectedTintColor = selectedColor }
            if glass.unselectedTintColor != normalColor { glass.unselectedTintColor = normalColor }
            glass.ngApplySelection(selected)
        }
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        nativeMask.frame = bar.bounds
        if bar.layer.mask !== nativeMask { bar.layer.mask = nativeMask }
        glass.alpha = bar.alpha
        glass.isHidden = false
        CATransaction.commit()
        glass.isUserInteractionEnabled = true
        glass.accessibilityElementsHidden = false
        presented = true
        updateDots()
    }

    private func updateDots() {
        guard data.count == 4 else { return }
        // Dots have no text; keep them out of the library's badge/title rasterization.
        for index in 0..<4 {
            let dot = dots[index]
            let rtl = glass.effectiveUserInterfaceLayoutDirection == .rightToLeft
            let slot = rtl ? 3 - index : index
            let width = glass.bounds.width / 4
            dot.frame = CGRect(x: width * (CGFloat(slot) + 0.5) + 11, y: 6, width: 6, height: 6)
            dot.isHidden = !data[index].redDot || data[index].badge?.isEmpty == false
            glass.bringSubviewToFront(dot)
        }
    }

    func detach() {
        guard !stopped else { return }
        stopped = true
        timer?.invalidate()
        timer = nil
        if let bar = native, bar.layer.mask === nativeMask {
            CATransaction.begin()
            CATransaction.setDisableActions(true)
            bar.layer.mask = originalMask
            CATransaction.commit()
        }
        glass.ngGlassDidPresent = nil
        glass.ngApplyHostFrame(.zero) // the stable library cancels an in-flight drag on host-frame change
        glass.removeFromSuperview()
        presented = false
    }

    private func activate(_ index: Int) -> Int? {
        guard !stopped, !activationPending, let bar = native,
              let before = NGWeChatCopyTabs(bar), data.indices.contains(index),
              before.entries.count == 4, before.entries[index].enabled,
              ObjectIdentifier(before.entries[index].identity as AnyObject) == data[index].identity else { return nil }
        activationPending = true
        defer {
            DispatchQueue.main.async { [weak self] in
                guard let self, let bar = self.native, !self.stopped else { return }
                self.activationPending = false
                WeChatTabsBridge.update(bar)
            }
        }
        let result = NGWeChatActivateTab(bar, index)
        return (0..<4).contains(result) ? result : nil
    }
}

@MainActor @objc(NGWeChatTabsBridge) final class WeChatTabsBridge: NSObject {
    private static let states = NSMapTable<UIView, WeChatTabsState>.weakToStrongObjects()
    private static let updating = NSHashTable<UIView>.weakObjects()
    private static let observed = NSHashTable<UIView>.weakObjects()
    private static let lifecycle: [NSObjectProtocol] = [UIApplication.didBecomeActiveNotification,
        UIApplication.didEnterBackgroundNotification,
        UIAccessibility.voiceOverStatusDidChangeNotification,
        UIAccessibility.reduceTransparencyStatusDidChangeNotification].map { name in
        NotificationCenter.default.addObserver(forName: name, object: nil, queue: .main) { _ in
            DispatchQueue.main.async { for bar in observed.allObjects { update(bar) } }
        }
    }

    @objc(usesOverlay:) static func usesOverlay(_ bar: UIView) -> Bool {
        states.object(forKey: bar)?.presented == true
    }

    @objc(detach:) static func detach(_ bar: UIView) {
        states.object(forKey: bar)?.detach()
        states.removeObject(forKey: bar)
    }

    private static func layoutFrame(_ bar: UIView, window: UIWindow, parent: UIView) -> CGRect? {
        guard window.traitCollection.userInterfaceIdiom == .phone else { return nil }
        var ancestor: UIView? = bar
        while let view = ancestor {
            guard !view.isHidden, view.alpha > 0.02 else { return nil }
            if view === window { break }
            ancestor = view.superview
        }
        let box = bar.convert(bar.bounds, to: window)
        guard box.width.isFinite, box.height.isFinite, box.minX.isFinite, box.minY.isFinite,
              box.width >= 260, box.width >= window.bounds.width * 0.9,
              (40...112).contains(box.height), box.intersects(window.bounds),
              abs(box.maxY - window.bounds.maxY) <= window.safeAreaInsets.bottom + 12 else { return nil }
        let rect = CGRect(x: box.minX + 14, y: window.bounds.maxY - window.safeAreaInsets.bottom + 5 - 63,
                          width: box.width - 28, height: 63)
        return parent.convert(rect, from: window)
    }

    @objc(update:) static func update(_ bar: UIView) {
        guard Thread.isMainThread, NGIsWeChatProcess(), !NGSystemTabIsCapturing(), !updating.contains(bar) else { return }
        updating.add(bar)
        defer { updating.remove(bar) }
        observed.add(bar)
        _ = lifecycle
        guard UIApplication.shared.applicationState != .background,
              !UIAccessibility.isVoiceOverRunning, !UIAccessibility.isReduceTransparencyEnabled,
              let window = bar.window, let parent = bar.superview,
              bar.isUserInteractionEnabled,
              let frame = layoutFrame(bar, window: window, parent: parent),
              let snapshot = NGWeChatCopyTabs(bar), snapshot.entries.count == 4,
              (0..<4).contains(snapshot.selectedIndex), Bundle.hasTabMetalResources else {
            detach(bar)
            return
        }
        let state: WeChatTabsState
        if let current = states.object(forKey: bar) {
            state = current
        } else {
            state = WeChatTabsState(bar)
            states.setObject(state, forKey: bar)
            state.attach(bar, parent: parent, frame: frame)
        }
        state.glass.semanticContentAttribute = bar.effectiveUserInterfaceLayoutDirection == .rightToLeft ? .forceRightToLeft : .forceLeftToRight
        state.apply(snapshot, bar: bar, parent: parent, frame: frame)
    }
}

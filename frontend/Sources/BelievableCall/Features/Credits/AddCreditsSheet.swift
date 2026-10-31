#if canImport(SwiftUI)
import SwiftUI

/// Bottom-sheet credit-package picker. Presented from the Add Credits button on
/// Settings. Visual style matches the app's quiet, glassy design; the package
/// catalog and grant are backend-driven.
public struct AddCreditsSheet: View {
    @Bindable var vm: CreditPackagesViewModel
    let onClose: () -> Void
    let onAcquired: (CreditAcquisition) -> Void

    public init(vm: CreditPackagesViewModel,
                onClose: @escaping () -> Void,
                onAcquired: @escaping (CreditAcquisition) -> Void) {
        self.vm = vm
        self.onClose = onClose
        self.onAcquired = onAcquired
    }

    public var body: some View {
        VStack(spacing: 0) {
            header
            content
        }
        .background(Theme.backgroundGradient.ignoresSafeArea())
        .task { if vm.packages.isEmpty { await vm.load() } }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Add Credits").font(.title2.bold())
                    Text("Choose a package")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    if let bonus = vm.bonusNote {
                        Label(bonus, systemImage: "gift.fill")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Theme.success)
                            .padding(.top, Spacing.xs)
                    }
                }
                Spacer()
                Button { onClose() } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Close")
            }
        }
        .padding(Spacing.l)
    }

    @ViewBuilder private var content: some View {
        switch vm.phase {
        case .idle, .loadingPackages:
            Spacer()
            ProgressView().padding(Spacing.xl)
            Spacer()
        default:
            if vm.didFailToLoad {
                loadFailure
            } else if vm.isEmptyCatalog {
                emptyState
            } else {
                packageList
            }
        }
    }

    private var packageList: some View {
        VStack(spacing: Spacing.m) {
            ScrollView {
                VStack(spacing: Spacing.s) {
                    ForEach(vm.packages) { package in
                        PackageCard(package: package,
                                    price: vm.price(for: package),
                                    isSelected: package.code == vm.selectedCode) {
                            vm.select(package.code)
                            Haptics.play(.impact)
                        }
                    }
                }
                .padding(.horizontal, Spacing.l)
            }
            footer
        }
    }

    private var footer: some View {
        VStack(spacing: Spacing.s) {
            if let error = vm.errorMessage {
                ErrorBanner(error)
            }
            if let notice = vm.unredeemedNotice ?? vm.pendingNotice {
                Text(notice)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }
            PrimaryButton(vm.primaryButtonTitle, isLoading: vm.isSubmitting) {
                Haptics.play(.impact)
                Task {
                    if await vm.acquire(), let granted = vm.lastGranted {
                        onAcquired(granted)
                    }
                }
            }
            .disabled(!vm.canSubmit)
            .opacity(vm.canSubmit ? 1 : 0.5)
            if let note = vm.costsNote {
                Text(note)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
        }
        .padding(.horizontal, Spacing.l)
        .padding(.bottom, Spacing.l)
    }

    private var loadFailure: some View {
        VStack(spacing: Spacing.m) {
            Spacer()
            if let error = vm.errorMessage { ErrorBanner(error) }
            PrimaryButton(String(localized: "Try again")) { Task { await vm.load() } }
            Spacer()
        }
        .padding(Spacing.l)
    }

    private var emptyState: some View {
        VStack(spacing: Spacing.s) {
            Spacer()
            Image(systemName: "creditcard")
                .font(.system(size: 36))
                .foregroundStyle(.secondary)
            Text("No credit packages are available right now.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Spacer()
        }
        .padding(Spacing.xl)
    }
}

struct PackageCard: View {
    let package: CreditPackage
    let price: String
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            Card {
                HStack(spacing: Spacing.m) {
                    VStack(alignment: .leading, spacing: Spacing.xs) {
                        Text(package.displayName).font(.headline)
                        Text(price)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    if let badge = package.badgeText {
                        Text(badge)
                            .font(.caption.weight(.semibold))
                            .padding(.horizontal, Spacing.s)
                            .padding(.vertical, 2)
                            .background(Theme.success.opacity(0.15))
                            .foregroundStyle(Theme.success)
                            .clipShape(Capsule())
                    }
                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.title3)
                        .foregroundStyle(isSelected ? Theme.accent : Color.secondary)
                }
            }
        }
        .buttonStyle(.plain)
        .overlay(
            RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
                .strokeBorder(isSelected ? Theme.accent : Color.clear, lineWidth: 2)
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(package.displayName), \(price)")
        .accessibilityAddTraits(isSelected ? [.isButton, .isSelected] : .isButton)
    }
}

struct AddCreditsSheet_Previews: PreviewProvider {
    static var previews: some View {
        AddCreditsSheet(vm: CreditPackagesViewModel(service: MockCreditPackagesService()),
                        onClose: {}, onAcquired: { _ in })
    }
}
#endif

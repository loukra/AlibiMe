#if canImport(SwiftUI)
import SwiftUI

/// The template editor, for new and existing templates. A new one goes through
/// three tile steps (who calls, why, how urgent) to an overview; an existing one
/// opens on the overview, where each answer can be changed. The rarer choices
/// sit under "More options". The backend composes the wording from the choices.
public struct CustomTemplateEditorView: View {
    @Bindable var vm: CustomTemplateEditorViewModel
    let onClose: () -> Void
    /// Saved, reset or deleted: the list reloads.
    let onFinished: () -> Void
    @State private var showMoreOptions = false
    @State private var confirmRemove = false

    public init(vm: CustomTemplateEditorViewModel,
                onClose: @escaping () -> Void,
                onFinished: @escaping () -> Void) {
        self.vm = vm
        self.onClose = onClose
        self.onFinished = onFinished
    }

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Spacing.l) {
                    if let options = vm.options {
                        if !vm.isEditing && vm.step != .overview { progress }
                        switch vm.step {
                        case .who: whoStep
                        case .why: whyStep
                        case .urgency: urgencyStep(options)
                        case .overview: overview(options)
                        }
                    } else if vm.errorMessage == nil {
                        HStack { Spacer(); ProgressView(); Spacer() }.padding(.top, Spacing.xl)
                    }
                    if let error = vm.errorMessage { ErrorBanner(error) }
                }
                .padding(Spacing.m)
            }
            // Each step is its own page and starts at the top.
            .id(vm.step)
            .bcScreenBackground()
            .navigationTitle(vm.isEditing ? "Edit alibi" : "New alibi")
            .bcInlineNavTitle()
            .toolbar { toolbar }
            .task { if vm.options == nil { await vm.load() } }
            .confirmationDialog(removeTitle, isPresented: $confirmRemove, titleVisibility: .visible) {
                Button(vm.canReset ? "Reset" : "Delete", role: .destructive) {
                    Task { if await vm.remove() { onFinished() } }
                }
            } message: {
                Text(vm.canReset
                     ? "Your changes are removed and the original alibi comes back."
                     : "This alibi is removed. Past calls and texts stay in History.")
            }
        }
    }

    @ToolbarContentBuilder private var toolbar: some ToolbarContent {
        ToolbarItem(placement: .cancellationAction) {
            if vm.canGoBack {
                Button { vm.back() } label: { Label("Back", systemImage: "chevron.left") }
            } else {
                Button("Cancel", action: onClose)
            }
        }
        if vm.step == .overview {
            ToolbarItem(placement: .confirmationAction) {
                if vm.isSubmitting {
                    ProgressView()
                } else {
                    Button("Save") {
                        Task { if await vm.submit() != nil { onFinished() } }
                    }
                    .disabled(!vm.canSubmit)
                }
            }
        }
    }

    private var removeTitle: String {
        vm.canReset ? String(localized: "Reset to the original?") : String(localized: "Delete this alibi?")
    }

    // MARK: Steps

    private var progress: some View {
        HStack(spacing: Spacing.xs) {
            ForEach(CustomTemplateEditorViewModel.Step.allCases, id: \.self) { step in
                Capsule()
                    .fill(step.rawValue <= vm.step.rawValue ? Theme.accent : Theme.accent.opacity(0.18))
                    .frame(height: 4)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("Step \(vm.step.rawValue + 1) of \(CustomTemplateEditorViewModel.Step.allCases.count)")
    }

    private var whoStep: some View {
        VStack(alignment: .leading, spacing: Spacing.m) {
            StepTitle(String(localized: "Who calls?"), String(localized: "The person your phone shows."))
            ForEach(vm.personaGroups, id: \.title) { group in
                SectionHeader(CustomTemplateEditorViewModel.groupTitle(group.title))
                TileGrid(group.options.map { option in
                    Tile(id: option.code, title: vm.personaLabel(option.code))
                }, selected: vm.draft.persona, onSelect: vm.choosePersona)
            }
        }
    }

    private var whyStep: some View {
        VStack(alignment: .leading, spacing: Spacing.m) {
            StepTitle(String(localized: "Why?"), String(localized: "What \(vm.personaPhrase) needs from you."))
            ForEach(vm.reasonGroups, id: \.title) { group in
                SectionHeader(CustomTemplateEditorViewModel.groupTitle(group.title))
                TileGrid(group.options.map { option in
                    Tile(id: option.code, title: vm.reasonLabel(option.code))
                }, selected: vm.draft.reason, onSelect: vm.chooseReason)
            }
        }
    }

    private func urgencyStep(_ options: TemplateOptions) -> some View {
        VStack(alignment: .leading, spacing: Spacing.m) {
            StepTitle(String(localized: "How urgent?"), String(localized: "How hard it pulls you out."))
            TileGrid(options.urgencies.map { code in
                let urgency = UrgencyCopy(code)
                return Tile(id: code, title: urgency.title, subtitle: urgency.subtitle,
                            systemImage: urgency.systemImage)
            }, selected: vm.draft.urgency, onSelect: vm.chooseUrgency)
        }
    }

    // MARK: Overview

    private func overview(_ options: TemplateOptions) -> some View {
        VStack(alignment: .leading, spacing: Spacing.l) {
            Card {
                HStack(spacing: Spacing.m) {
                    IconBadge(TemplateCategory(wireValue: vm.draft.category).systemImage)
                    Text(vm.summary)
                        .font(.body.weight(.medium))
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            VStack(alignment: .leading, spacing: Spacing.s) {
                SectionHeader("Scenario")
                AnswerRow(question: String(localized: "Who calls?"), answer: vm.personaLabel(vm.draft.persona)) {
                    vm.go(to: .who)
                }
                AnswerRow(question: String(localized: "Why?"), answer: vm.reasonLabel(vm.draft.reason)) {
                    vm.go(to: .why)
                }
                AnswerRow(question: String(localized: "How urgent?"), answer: UrgencyCopy(vm.draft.urgency).title) {
                    vm.go(to: .urgency)
                }
            }

            VStack(alignment: .leading, spacing: Spacing.s) {
                SectionHeader("Name")
                Card {
                    TextField("Alibi name", text: $vm.draft.displayName)
                        .font(.body)
                }
            }

            VStack(alignment: .leading, spacing: Spacing.s) {
                SectionHeader("Works as")
                HStack(spacing: Spacing.s) {
                    ForEach(options.channels) { channel in
                        let on = vm.draft.channels.contains(channel)
                        Button {
                            vm.toggle(channel, on: !on)
                            Haptics.play(.impact)
                        } label: {
                            TileLabel(title: channel.title,
                                      subtitle: channel == .call ? String(localized: "Your phone rings") : String(localized: "A message arrives"),
                                      systemImage: channel.outlineSymbol, isSelected: on)
                        }
                        .buttonStyle(.plain)
                        .accessibilityAddTraits(on ? [.isButton, .isSelected] : .isButton)
                    }
                }
            }

            VStack(alignment: .leading, spacing: Spacing.s) {
                Button {
                    withAnimation(.snappy) { showMoreOptions.toggle() }
                } label: {
                    HStack {
                        SectionHeader("More options")
                        Spacer()
                        Image(systemName: "chevron.down")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.secondary)
                            .rotationEffect(.degrees(showMoreOptions ? 180 : 0))
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                if showMoreOptions { moreOptions(options) }
            }

            Text("The wording is written from your choices. You can't type the call or text yourself.")
                .font(.footnote)
                .foregroundStyle(.secondary)

            if vm.canReset || vm.canDelete {
                Button(role: .destructive) { confirmRemove = true } label: {
                    Label(vm.canReset ? "Reset to original" : "Delete alibi",
                          systemImage: vm.canReset ? "arrow.uturn.backward" : "trash")
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Spacing.s)
                }
                .buttonStyle(.bordered)
                .tint(Theme.destructive)
                .disabled(vm.isSubmitting)
            }
        }
    }

    private func moreOptions(_ options: TemplateOptions) -> some View {
        Card {
            VStack(spacing: Spacing.s) {
                optionMenu(String(localized: "Outcome"), $vm.draft.outcome, options.outcomes)
                optionMenu(String(localized: "Setting"), $vm.draft.setting, options.settings)
                codeMenu(String(localized: "Tone"), $vm.draft.tone, options.tones)
                codeMenu(String(localized: "Formality"), $vm.draft.formality, options.formalities)
                codeMenu(String(localized: "Detail"), $vm.draft.detailProfile, options.detailProfiles)
                codeMenu(String(localized: "Discretion"), $vm.draft.discretionLevel, options.discretionLevels)
                optionMenu(String(localized: "Expected reply"), $vm.draft.expectedResponse, options.expectedResponses)
                optionMenu(String(localized: "Follow-up"), $vm.draft.followupBehavior, options.followupBehaviors)
                codeMenu(String(localized: "Continuity"), $vm.draft.continuityScope, options.continuityScopes)
                if vm.draft.channels.contains(.call) {
                    codeMenu(String(localized: "Voice"), $vm.draft.voiceStyle, options.voiceStyles)
                    Stepper(String(localized: "Call length: \(vm.draft.callMaxSeconds) s"),
                            value: $vm.draft.callMaxSeconds,
                            in: options.callSecondsMin...options.callSecondsMax,
                            step: 10)
                        .font(.subheadline)
                }
                if !options.contextModules.isEmpty {
                    Divider()
                    Text("Use details from my Profile")
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(options.contextModules, id: \.self) { module in
                        Toggle(CustomTemplateEditorViewModel.humanized(module), isOn: Binding(
                            get: { vm.draft.contextModules.contains(module) },
                            set: { on in
                                if on { vm.draft.contextModules.insert(module) }
                                else { vm.draft.contextModules.remove(module) }
                            }
                        ))
                        .font(.subheadline)
                        .tint(Theme.accent)
                    }
                }
            }
        }
    }

    private func optionMenu(_ title: String, _ binding: Binding<String>,
                            _ options: [TemplateOption]) -> some View {
        menuRow(title, binding, options.map { ($0.code, $0.label) })
    }

    private func codeMenu(_ title: String, _ binding: Binding<String>, _ codes: [String]) -> some View {
        menuRow(title, binding, codes.map { ($0, vm.options?.labels[$0] ?? CustomTemplateEditorViewModel.humanized($0)) })
    }

    private func menuRow(_ title: String, _ binding: Binding<String>,
                         _ items: [(code: String, label: String)]) -> some View {
        HStack {
            Text(title).font(.subheadline)
            Spacer(minLength: Spacing.s)
            Picker(title, selection: binding) {
                ForEach(items, id: \.code) { Text($0.label).tag($0.code) }
            }
            .labelsHidden()
            .tint(Theme.accent)
            .lineLimit(1)
            .fixedSize()
        }
        .frame(minHeight: 36)
    }
}

// MARK: - Pieces

private struct StepTitle: View {
    let title: String
    let subtitle: String
    init(_ title: String, _ subtitle: String) {
        self.title = title
        self.subtitle = subtitle
    }
    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            Text(title).font(.title2.bold())
            Text(subtitle).font(.subheadline).foregroundStyle(.secondary)
        }
    }
}

private struct Tile: Identifiable {
    let id: String
    let title: String
    var subtitle: String?
    var systemImage: String?
}

/// Two equal columns of equally sized tiles; tapping one answers the step.
private struct TileGrid: View {
    let tiles: [Tile]
    let selected: String
    let onSelect: (String) -> Void

    init(_ tiles: [Tile], selected: String, onSelect: @escaping (String) -> Void) {
        self.tiles = tiles
        self.selected = selected
        self.onSelect = onSelect
    }

    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: Spacing.s),
                            GridItem(.flexible(), spacing: Spacing.s)],
                  spacing: Spacing.s) {
            ForEach(tiles) { tile in
                Button {
                    Haptics.play(.impact)
                    onSelect(tile.id)
                } label: {
                    TileLabel(title: tile.title, subtitle: tile.subtitle,
                              systemImage: tile.systemImage, isSelected: tile.id == selected)
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(tile.id == selected ? [.isButton, .isSelected] : .isButton)
            }
        }
    }
}

/// A tile: always the same height, whether its title takes one line or two.
private struct TileLabel: View {
    let title: String
    var subtitle: String?
    var systemImage: String?
    let isSelected: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            if let systemImage {
                // A fixed box: symbols differ in height, tiles must not.
                Image(systemName: systemImage)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(Theme.accent)
                    .frame(width: 24, height: 24, alignment: .leading)
                    .padding(.bottom, 2)
            }
            Text(title)
                .font(.subheadline.weight(.semibold))
                .lineLimit(2, reservesSpace: subtitle == nil)
                .multilineTextAlignment(.leading)
            if let subtitle {
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Spacing.m)
        .background(.ultraThinMaterial,
                    in: RoundedRectangle(cornerRadius: Radius.control, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
                .strokeBorder(isSelected ? Theme.accent : Theme.glassBorder,
                              lineWidth: isSelected ? 2 : 1)
        )
        .contentShape(Rectangle())
    }
}

/// One answer on the overview; tapping it reopens that step.
private struct AnswerRow: View {
    let question: String
    let answer: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Card {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(question).font(.caption).foregroundStyle(.secondary)
                        Text(answer).font(.body.weight(.semibold)).lineLimit(1)
                    }
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityHint("Change")
    }
}

/// Plain-language urgency, instead of the raw codes.
private struct UrgencyCopy {
    let title: String
    let subtitle: String
    let systemImage: String

    init(_ code: String) {
        switch code {
        case "low": (title, subtitle, systemImage) = (String(localized: "No rush"), String(localized: "Whenever you can"), "tortoise")
        case "high": (title, subtitle, systemImage) = (String(localized: "Urgent"), String(localized: "Needs you soon"), "exclamationmark.circle")
        case "immediate": (title, subtitle, systemImage) = (String(localized: "Right now"), String(localized: "Drop everything"), "bolt")
        default: (title, subtitle, systemImage) = (String(localized: "Soon"), String(localized: "In the next minutes"), "clock")
        }
    }
}

struct CustomTemplateEditorView_Previews: PreviewProvider {
    static var previews: some View {
        CustomTemplateEditorView(vm: CustomTemplateEditorViewModel(service: MockTemplateService()),
                                 onClose: {}, onFinished: {})
    }
}
#endif

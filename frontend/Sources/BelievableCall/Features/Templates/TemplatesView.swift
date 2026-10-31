#if canImport(SwiftUI)
import SwiftUI

/// The Templates library page: the user's own templates first, then the
/// built-in ones by category, each as its own card (like the picker on Home).
/// Tapping a card edits it (a built-in one can be reset later); ＋ creates a
/// new one; own templates are also deleted with a swipe.
public struct TemplatesView: View {
    @Bindable var vm: TemplatesViewModel
    /// Non-nil while the editor sheet is open. `.sheet(item:)` hands the view
    /// model straight to the sheet; `isPresented` + `if let` rendered an empty
    /// sheet on first open because the closure read a stale `nil`.
    @State private var editorVM: CustomTemplateEditorViewModel?

    public init(vm: TemplatesViewModel) { self.vm = vm }

    public var body: some View {
        List {
            if let error = vm.errorMessage {
                Section { ErrorBanner(error) }
            }
            if vm.showProfileNote {
                Section {
                    Label("Fill in your Profile so your alibis fit your life.",
                          systemImage: "person.crop.circle")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            if !vm.customTemplates.isEmpty {
                Section {
                    ForEach(vm.customTemplates) { row($0) }
                        .onDelete { offsets in
                            let items = offsets.map { vm.customTemplates[$0] }
                            Task { for item in items { await vm.delete(item) } }
                        }
                } header: { SectionHeader("Your alibis") }
            }
            ForEach(vm.systemTemplatesByCategory, id: \.category) { group in
                Section {
                    ForEach(group.templates) { row($0) }
                } header: { SectionHeader(group.category.title) }
            }
        }
        .listStyle(.plain)
        .bcClearScrollBackground()
        .bcTabBarClearance()
        .bcScreenBackground()
        .navigationTitle("Alibis")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    editorVM = vm.makeEditorViewModel()
                } label: {
                    Image(systemName: "plus")
                }
                .accessibilityLabel("New alibi")
            }
        }
        .task { await vm.load() }
        .refreshable { await vm.load() }
        .sheet(item: $editorVM) { editor in
            CustomTemplateEditorView(
                vm: editor,
                onClose: { editorVM = nil },
                onFinished: {
                    editorVM = nil
                    Task { await vm.editorFinished() }
                }
            )
        }
    }

    private func row(_ template: TemplateSummary) -> some View {
        Button {
            editorVM = vm.makeEditorViewModel(editing: template)
        } label: {
            TemplateRow(template: template)
        }
        .buttonStyle(.plain)
        .bcCardRow()
        .accessibilityHint("Edit")
    }
}

struct TemplateRow: View {
    let template: TemplateSummary

    var body: some View {
        ListCardRow(icon: template.category.systemImage,
                    title: template.displayName,
                    detail: template.description ?? "") {
            if template.isEdited { EditedTag() }
        } footer: {
            ChannelGlyphs(channels: template.supportedChannels)
        }
        .accessibilityElement(children: .combine)
    }
}

/// Marks a built-in template the user changed (it can be reset in the editor).
struct EditedTag: View {
    var body: some View {
        Text("Edited")
            .font(.caption.weight(.semibold))
            .padding(.horizontal, Spacing.s)
            .padding(.vertical, 3)
            .foregroundStyle(Theme.accent)
            .background(Theme.accent.opacity(0.12), in: Capsule())
    }
}

/// Round badge with the template's category symbol (briefcase for work, …).
struct TemplateBadge: View {
    let category: TemplateCategory

    var body: some View { IconBadge(category.systemImage) }
}

/// A quiet line naming the channels a template supports, call first. Built by
/// hand: a `Label` inside a List spreads icon and title far apart.
struct ChannelGlyphs: View {
    let channels: Set<Channel>

    var body: some View {
        HStack(spacing: Spacing.m) {
            ForEach(Channel.allCases.filter(channels.contains)) { channel in
                HStack(spacing: 4) {
                    Image(systemName: channel.outlineSymbol)
                    Text(channel.title)
                }
            }
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .accessibilityElement()
        .accessibilityLabel(Channel.allCases.filter(channels.contains).map(\.title).joined(separator: " and "))
    }
}

extension Channel {
    /// The light outline symbol used in lists; buttons keep `systemImage`.
    var outlineSymbol: String {
        switch self {
        case .call: return "phone"
        case .text: return "bubble.left"
        }
    }
}

struct TemplatesView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationStack {
            TemplatesView(vm: TemplatesViewModel(service: MockTemplateService()))
        }
    }
}
#endif

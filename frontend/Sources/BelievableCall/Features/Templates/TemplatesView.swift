#if canImport(SwiftUI)
import SwiftUI

/// The Templates library page: the user's own templates first, then the
/// built-in ones by category, each as its own card (like the picker on Home).
/// ＋ creates a new one; own templates are deleted with a swipe.
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
                    Label("You can configure your Profile for more tailored custom templates.",
                          systemImage: "person.crop.circle")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            if !vm.customTemplates.isEmpty {
                Section {
                    ForEach(vm.customTemplates) { TemplateRow(template: $0).bcCardRow() }
                        .onDelete { offsets in
                            let items = offsets.map { vm.customTemplates[$0] }
                            Task { for item in items { await vm.delete(item) } }
                        }
                } header: { SectionHeader("Your templates") }
            }
            ForEach(vm.systemTemplatesByCategory, id: \.category) { group in
                Section {
                    ForEach(group.templates) { TemplateRow(template: $0).bcCardRow() }
                } header: { SectionHeader(group.category.title) }
            }
        }
        .listStyle(.plain)
        .bcClearScrollBackground()
        .bcTabBarClearance()
        .bcScreenBackground()
        .navigationTitle("Templates")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    editorVM = vm.makeEditorViewModel()
                } label: {
                    Image(systemName: "plus")
                }
                .accessibilityLabel("New template")
            }
        }
        .task { await vm.load() }
        .refreshable { await vm.load() }
        .sheet(item: $editorVM) { editor in
            CustomTemplateEditorView(
                vm: editor,
                onClose: { editorVM = nil },
                onCreated: { _ in
                    editorVM = nil
                    Task { await vm.load() }
                }
            )
        }
    }
}

struct TemplateRow: View {
    let template: TemplateSummary

    var body: some View {
        ListCardRow(icon: template.category.systemImage,
                    title: template.displayName,
                    detail: template.description ?? "") {
            ChannelGlyphs(channels: template.supportedChannels)
        }
        .accessibilityElement(children: .combine)
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

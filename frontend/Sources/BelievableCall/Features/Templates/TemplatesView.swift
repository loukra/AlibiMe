#if canImport(SwiftUI)
import SwiftUI

/// The Templates library page: built-in templates and the user's own custom
/// templates, with a ＋ to create a new one and swipe-to-delete for customs.
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
                Section("Your templates") {
                    ForEach(vm.customTemplates) { TemplateRow(template: $0) }
                        .onDelete { offsets in
                            let items = offsets.map { vm.customTemplates[$0] }
                            Task { for item in items { await vm.delete(item) } }
                        }
                }
            }
            Section("Built-in templates") {
                ForEach(vm.systemTemplates) { TemplateRow(template: $0) }
            }
        }
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
        HStack(spacing: Spacing.m) {
            TemplateBadge(category: template.category)
            VStack(alignment: .leading, spacing: 2) {
                Text(template.displayName).font(.body.weight(.semibold))
                if let description = template.description {
                    Text(description)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                ChannelGlyphs(channels: template.supportedChannels)
                    .padding(.top, 2)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.vertical, Spacing.xs)
        .accessibilityElement(children: .combine)
    }
}

/// Round badge with the template's category symbol (briefcase for work, …).
struct TemplateBadge: View {
    let category: TemplateCategory

    var body: some View {
        Image(systemName: category.systemImage)
            .font(.body.weight(.semibold))
            .foregroundStyle(Theme.accent)
            .frame(width: 40, height: 40)
            .background(Theme.accent.opacity(0.14), in: Circle())
            .accessibilityHidden(true)
    }
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

#if canImport(SwiftUI)
import SwiftUI

/// The Templates library page: built-in templates and the user's own custom
/// templates, with a ＋ to create a new one and swipe-to-delete for customs.
public struct TemplatesView: View {
    @Bindable var vm: TemplatesViewModel
    @State private var editorVM: CustomTemplateEditorViewModel?
    @State private var showEditor = false

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
                    showEditor = true
                } label: {
                    Image(systemName: "plus")
                }
                .accessibilityLabel("New template")
            }
        }
        .task { await vm.load() }
        .refreshable { await vm.load() }
        .sheet(isPresented: $showEditor) {
            if let editorVM {
                CustomTemplateEditorView(
                    vm: editorVM,
                    onClose: { showEditor = false },
                    onCreated: { _ in
                        showEditor = false
                        Task { await vm.load() }
                    }
                )
            }
        }
    }
}

struct TemplateRow: View {
    let template: TemplateSummary

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            Text(template.displayName).font(.body.weight(.medium))
            if let description = template.description {
                Text(description).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            }
            HStack(spacing: Spacing.xs) {
                ForEach(Array(template.supportedChannels).sorted { $0.rawValue < $1.rawValue }) { channel in
                    Label(channel.title, systemImage: channel.systemImage)
                        .font(.caption2.weight(.medium))
                        .padding(.horizontal, Spacing.s)
                        .padding(.vertical, 2)
                        .background(Theme.accent.opacity(0.12))
                        .foregroundStyle(Theme.accent)
                        .clipShape(Capsule())
                }
            }
        }
        .padding(.vertical, 2)
        .accessibilityElement(children: .combine)
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

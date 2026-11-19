# Compact CMS Navigation Design

The CMS keeps its existing two-page information architecture: Articles and Administrators remain in the left sidebar on desktop and in the horizontal header on narrow mobile screens. The change is deliberately visual and semantic; routes, authentication, page content, and article/user actions stay unchanged.

Desktop navigation should read as one quiet product menu rather than two independent cards. Rows become slightly shorter, borders disappear, and the active page uses the existing graphite control surface with white text and no colored indicator. Hover and keyboard-focus states remain distinct. The Articles icon becomes a compact content-list glyph; Administrators becomes a light ID-card glyph, clarifying that the second page manages people and access without the visual weight of a shield.

The shell uses a consistent radius scale drawn from the current layout: 10px for controls, 12px for panels, 16px for desktop dialogs, 12px for mobile dialogs, and 16px for the main workspace corner. Circular avatars, status dots, and pills remain circular. The shared non-semantic blue accent becomes the existing light neutral gray, including primary actions, focus, and the Total marker; semantic success and danger colors remain green and red.

The base template owns link labels and active state. Both links keep explicit accessible names and tooltips when the sidebar collapses to icons. The breadcrumb becomes a semantic navigation landmark with a working CMS home link. On phone widths, page labels return in the horizontal navigation and a compact sign-out action remains reachable.

No JavaScript or dependency is added. Verification covers the exact current link on both pages, persistent accessible names, breadcrumb semantics, the editor-error page's Articles state, and responsive browser checks at the existing 780px and 560px breakpoints.

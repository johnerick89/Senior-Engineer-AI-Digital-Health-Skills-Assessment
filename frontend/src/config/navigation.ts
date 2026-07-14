export type AppRoute = "/" | "/upload" | "/assignment" | "/usage";

export type NavItem = {
  href: AppRoute;
  label: string;
  mobileTitle: string;
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Chat", mobileTitle: "Chat" },
  { href: "/upload", label: "Upload documents", mobileTitle: "Upload" },
  { href: "/usage", label: "Usage", mobileTitle: "Usage" },
  { href: "/assignment", label: "Assignment brief", mobileTitle: "Assignment" },
];

export function mobileTitleForPath(pathname: string): string {
  return (
    NAV_ITEMS.find((item) => item.href === pathname)?.mobileTitle ?? "Chat"
  );
}

import IndexView from "./IndexView";

// Static export: one prebuilt shell; the host rewrites /indices/<slug> to it and IndexView reads the slug from the URL.
export function generateStaticParams() {
  return [{ slug: "_" }];
}

export default function IndexPage() {
  return <IndexView />;
}

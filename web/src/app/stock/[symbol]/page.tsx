import StockView from "./StockView";

// With static export, one shell page is prebuilt and the host rewrites /stock/* to it;
// StockView reads the real symbol from the URL in the browser.
export function generateStaticParams() {
  return [{ symbol: "_" }];
}

export default function StockPage() {
  return <StockView />;
}

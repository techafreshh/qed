import { Link, Route, Routes } from "react-router-dom";
import ClaimInput from "./views/ClaimInput";
import RunTrace from "./views/RunTrace";
import VerdictCard from "./views/VerdictCard";
import Notebook from "./views/Notebook";

export default function App(): JSX.Element {
  return (
    <div
      style={{
        maxWidth: 880,
        margin: "0 auto",
        padding: 16,
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 12,
          marginBottom: 16,
        }}
      >
        <Link to="/" style={{ textDecoration: "none", color: "inherit" }}>
          <h1 style={{ margin: 0 }}>QED</h1>
        </Link>
        <span style={{ color: "#64748b", fontSize: 14 }}>
          a second opinion for published science
        </span>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<ClaimInput />} />
          <Route path="/runs/:id" element={<RunTrace />} />
          <Route path="/runs/:id/verdict" element={<VerdictCard />} />
          <Route path="/runs/:id/notebook" element={<Notebook />} />
        </Routes>
      </main>
    </div>
  );
}

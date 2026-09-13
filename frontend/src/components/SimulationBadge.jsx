// Marks a constructed demonstration event, as the frontend specification
// requires. Screened events never carry it; every number on those is computed
// from the real catalog.
export default function SimulationBadge({ show, className = '' }) {
  if (!show) return null
  return (
    <span
      title="Constructed demonstration scenario: the ISS state is real, the debris object is not."
      className={`rounded px-2 py-0.5 text-[10px] font-semibold tracking-wide ${className}`}
      style={{ color: '#B794F6', backgroundColor: '#B794F61A', border: '1px solid #B794F640' }}
    >
      SIMULATION
    </span>
  )
}

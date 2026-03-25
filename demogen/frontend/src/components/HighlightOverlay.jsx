const HighlightOverlay = ({ highlight, elementDescription, animated }) => {
  const box = {
    x: Number.isFinite(Number(highlight?.x)) ? Number(highlight.x) : 25,
    y: Number.isFinite(Number(highlight?.y)) ? Number(highlight.y) : 25,
    width: Number.isFinite(Number(highlight?.width)) ? Number(highlight.width) : 50,
    height: Number.isFinite(Number(highlight?.height)) ? Number(highlight.height) : 50,
  };

  return (
    <>
      <div
        className="pointer-events-none absolute border-2 border-teal bg-teal/10 animate-pulseborder"
        style={{
          left: `${box.x}%`,
          top: `${box.y}%`,
          width: `${box.width}%`,
          height: `${box.height}%`,
        }}
      >
        <div className="absolute -top-8 left-0 rounded-full border border-teal/70 bg-[#06211e]/90 px-3 py-1 text-xs text-tealSoft">
          {elementDescription || "Main action area"}
        </div>

        {animated && (
          <div className="pointer-events-none absolute inset-0 overflow-visible">
            <div className="demo-cursor absolute left-[10%] top-[14%]">
              <div className="demo-cursor-arrow" />
              <div className="demo-click-ring" />
            </div>
          </div>
        )}
      </div>
    </>
  );
};

export default HighlightOverlay;

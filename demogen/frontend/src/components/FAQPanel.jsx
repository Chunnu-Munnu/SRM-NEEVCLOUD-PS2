const FAQPanel = ({ faqs }) => {
  if (!faqs?.length) {
    return null;
  }

  return (
    <section className="mt-4 rounded-xl border border-slate-700 bg-[#0e1827] p-4">
      <h3 className="text-lg font-semibold text-tealSoft">FAQs</h3>
      <div className="mt-3 space-y-3">
        {faqs.map((faq, idx) => (
          <details key={`${faq.question}-${idx}`} className="rounded-lg border border-slate-700 bg-[#101d30] p-3">
            <summary className="cursor-pointer text-sm font-medium text-slate-100">{faq.question}</summary>
            <p className="mt-2 text-sm text-slate-300">{faq.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
};

export default FAQPanel;

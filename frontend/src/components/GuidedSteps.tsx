/** Guided mode: a three-step coach that follows what the user has already done. */
interface Props {
  variableChosen: boolean;
  placeChosen: boolean;
  analyzed: boolean;
  variableName: string;
}

export const GuidedSteps = ({ variableChosen, placeChosen, analyzed, variableName }: Props) => {
  const steps = [
    { done: variableChosen, title: 'Choose a variable', hint: 'Pick what to investigate in the panel on the left. Precipitation is a good start.' },
    { done: placeChosen, title: 'Pick a place', hint: 'Click anywhere on Earth, or use the box tool to draw a region.' },
    { done: analyzed, title: 'Test for a trend', hint: `Press "Analyze trend" to test whether ${variableName.toLowerCase()} changed over time.` },
  ];
  const current = steps.findIndex((s) => !s.done);
  return (
    <div className="glass guided" role="status" aria-live="polite">
      <ol className="guided-steps">
        {steps.map((s, i) => (
          <li key={s.title} className={s.done ? 'done' : i === current ? 'current' : ''}>
            <span className="num">{s.done ? '✓' : i + 1}</span>
            <span className="label">{s.title}</span>
          </li>
        ))}
      </ol>
      <div className="guided-hint">
        {current === -1 ? 'Done! Read the result card, then try another place or a longer period to compare.' : steps[current].hint}
      </div>
    </div>
  );
};

import React from 'react';

interface DataRowProps {
  label: string;
  value: string | number;
  unit?: string;
}

export const DataRow: React.FC<DataRowProps> = ({ label, value, unit }) => {
  return (
    <div className="data-row">
      <span className="data-label">{label}</span>
      <div>
        <span className="data-value">{value}</span>
        {unit && <span className="data-unit">{unit}</span>}
      </div>
    </div>
  );
};

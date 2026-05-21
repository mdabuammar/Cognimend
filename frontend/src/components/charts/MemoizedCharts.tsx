import { memo, useMemo, useCallback, useRef, useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

// ===================================================
// Optimized Chart Wrapper with Resize Observer
// ===================================================

interface OptimizedChartContainerProps {
  children: React.ReactNode;
  height?: number | string;
  className?: string;
}

export const OptimizedChartContainer = memo(function OptimizedChartContainer({
  children,
  height = 300,
  className = '',
}: OptimizedChartContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        // Use contentRect for accurate dimensions
        const { width, height } = entry.contentRect;
        setDimensions({ width, height });
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => resizeObserver.disconnect();
  }, []);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ height: typeof height === 'number' ? `${height}px` : height }}
    >
      {dimensions.width > 0 && children}
    </div>
  );
});

// ===================================================
// Memoized Line Chart
// ===================================================

interface LineChartData {
  name: string;
  [key: string]: string | number;
}

interface OptimizedLineChartProps {
  data: LineChartData[];
  dataKeys: string[];
  colors?: string[];
  xAxisKey?: string;
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
  animate?: boolean;
}

export const OptimizedLineChart = memo(function OptimizedLineChart({
  data,
  dataKeys,
  colors = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300'],
  xAxisKey = 'name',
  height = 300,
  showGrid = true,
  showLegend = true,
  animate = false, // Disable animations by default for performance
}: OptimizedLineChartProps) {
  // Memoize processed data
  const processedData = useMemo(() => {
    // Only keep necessary fields
    return data.map((item) => {
      const result: Record<string, unknown> = { [xAxisKey]: item[xAxisKey] };
      dataKeys.forEach((key) => {
        result[key] = item[key];
      });
      return result;
    });
  }, [data, dataKeys, xAxisKey]);

  // Memoize lines
  const lines = useMemo(
    () =>
      dataKeys.map((key, index) => (
        <Line
          key={key}
          type="monotone"
          dataKey={key}
          stroke={colors[index % colors.length]}
          strokeWidth={2}
          dot={false}
          isAnimationActive={animate}
        />
      )),
    [dataKeys, colors, animate]
  );

  return (
    <OptimizedChartContainer height={height}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={processedData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          {showGrid && <CartesianGrid strokeDasharray="3 3" opacity={0.3} />}
          <XAxis dataKey={xAxisKey} tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--background))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
            }}
          />
          {showLegend && <Legend />}
          {lines}
        </LineChart>
      </ResponsiveContainer>
    </OptimizedChartContainer>
  );
});

// ===================================================
// Memoized Bar Chart
// ===================================================

interface OptimizedBarChartProps {
  data: LineChartData[];
  dataKeys: string[];
  colors?: string[];
  xAxisKey?: string;
  height?: number;
  stacked?: boolean;
  animate?: boolean;
}

export const OptimizedBarChart = memo(function OptimizedBarChart({
  data,
  dataKeys,
  colors = ['#8884d8', '#82ca9d', '#ffc658'],
  xAxisKey = 'name',
  height = 300,
  stacked = false,
  animate = false,
}: OptimizedBarChartProps) {
  const bars = useMemo(
    () =>
      dataKeys.map((key, index) => (
        <Bar
          key={key}
          dataKey={key}
          fill={colors[index % colors.length]}
          stackId={stacked ? 'stack' : undefined}
          isAnimationActive={animate}
        />
      )),
    [dataKeys, colors, stacked, animate]
  );

  return (
    <OptimizedChartContainer height={height}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey={xAxisKey} tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--background))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
            }}
          />
          <Legend />
          {bars}
        </BarChart>
      </ResponsiveContainer>
    </OptimizedChartContainer>
  );
});

// ===================================================
// Memoized Area Chart
// ===================================================

interface OptimizedAreaChartProps {
  data: LineChartData[];
  dataKeys: string[];
  colors?: string[];
  xAxisKey?: string;
  height?: number;
  stacked?: boolean;
  animate?: boolean;
}

export const OptimizedAreaChart = memo(function OptimizedAreaChart({
  data,
  dataKeys,
  colors = ['#8884d8', '#82ca9d', '#ffc658'],
  xAxisKey = 'name',
  height = 300,
  stacked = false,
  animate = false,
}: OptimizedAreaChartProps) {
  const areas = useMemo(
    () =>
      dataKeys.map((key, index) => (
        <Area
          key={key}
          type="monotone"
          dataKey={key}
          stroke={colors[index % colors.length]}
          fill={colors[index % colors.length]}
          fillOpacity={0.3}
          stackId={stacked ? 'stack' : undefined}
          isAnimationActive={animate}
        />
      )),
    [dataKeys, colors, stacked, animate]
  );

  return (
    <OptimizedChartContainer height={height}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey={xAxisKey} tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--background))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
            }}
          />
          <Legend />
          {areas}
        </AreaChart>
      </ResponsiveContainer>
    </OptimizedChartContainer>
  );
});

// ===================================================
// Memoized Pie Chart
// ===================================================

interface PieChartData {
  name: string;
  value: number;
}

interface OptimizedPieChartProps {
  data: PieChartData[];
  colors?: string[];
  height?: number;
  innerRadius?: number;
  outerRadius?: number;
  showLabel?: boolean;
  animate?: boolean;
}

export const OptimizedPieChart = memo(function OptimizedPieChart({
  data,
  colors = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#00C49F'],
  height = 300,
  innerRadius = 0,
  outerRadius = 80,
  showLabel = true,
  animate = false,
}: OptimizedPieChartProps) {
  const cells = useMemo(
    () =>
      data.map((_, index) => (
        <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
      )),
    [data.length, colors]
  );

  const renderLabel = useCallback(
    ({ name, percent }: { name: string; percent: number }) =>
      showLabel ? `${name}: ${(percent * 100).toFixed(0)}%` : null,
    [showLabel]
  );

  return (
    <OptimizedChartContainer height={height}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            paddingAngle={2}
            dataKey="value"
            label={renderLabel}
            isAnimationActive={animate}
          >
            {cells}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--background))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
            }}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </OptimizedChartContainer>
  );
});

// ===================================================
// Stat Card with Sparkline
// ===================================================

interface SparklineData {
  value: number;
}

interface StatCardWithSparklineProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  sparklineData?: SparklineData[];
  color?: string;
}

export const StatCardWithSparkline = memo(function StatCardWithSparkline({
  title,
  value,
  change,
  changeLabel,
  sparklineData = [],
  color = '#8884d8',
}: StatCardWithSparklineProps) {
  const isPositive = change !== undefined && change >= 0;

  return (
    <div className="p-4 bg-card rounded-lg border">
      <p className="text-sm text-muted-foreground">{title}</p>
      <div className="flex items-end justify-between mt-1">
        <div>
          <p className="text-2xl font-bold">{value}</p>
          {change !== undefined && (
            <p className={`text-sm ${isPositive ? 'text-green-500' : 'text-red-500'}`}>
              {isPositive ? '+' : ''}
              {change}% {changeLabel}
            </p>
          )}
        </div>
        {sparklineData.length > 0 && (
          <div className="w-20 h-10">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sparklineData}>
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={color}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
});

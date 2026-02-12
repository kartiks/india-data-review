import React from "react";
import { View, Text, StyleSheet, ScrollView, Dimensions } from "react-native";
import Svg, {
  Path,
  Circle,
  Text as SvgText,
  Line,
  Defs,
  LinearGradient,
  Stop,
  G,
} from "react-native-svg";
import Colors from "@/constants/colors";

interface LineDataset {
  data: number[];
  color: string;
  label: string;
}

interface LineChartProps {
  labels: string[];
  datasets: LineDataset[];
  height?: number;
  showArea?: boolean;
  formatValue?: (v: number) => string;
  title?: string;
  yAxisLabel?: string;
}

function defaultFormat(v: number): string {
  if (Math.abs(v) >= 100000) return `${(v / 100000).toFixed(1)}L`;
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(0)}K`;
  if (Math.abs(v) < 10) return v.toFixed(1);
  return v.toFixed(0);
}

export default function LineChart({
  labels,
  datasets,
  height = 220,
  showArea = false,
  formatValue = defaultFormat,
  title,
  yAxisLabel,
}: LineChartProps) {
  const yAxisWidth = 42;
  const chartTop = 12;
  const chartBottom = 24;
  const chartH = height - chartTop - chartBottom;
  const padding = 10;
  const screenWidth = Dimensions.get("window").width - 48;
  const pointSpacing = Math.max(40, (screenWidth - yAxisWidth) / Math.max(labels.length - 1, 1));
  const svgWidth = Math.max(
    yAxisWidth + padding * 2 + (labels.length - 1) * pointSpacing,
    screenWidth
  );

  const allValues = datasets.flatMap((ds) => ds.data.filter((v) => v !== 0));
  const maxVal = Math.max(...allValues, 1);
  const minVal = Math.min(...allValues, 0);
  const range = maxVal - minVal || 1;
  const paddedMin = minVal - range * 0.05;
  const paddedMax = maxVal + range * 0.05;
  const paddedRange = paddedMax - paddedMin || 1;

  const getY = (val: number) => {
    return chartTop + ((paddedMax - val) / paddedRange) * chartH;
  };
  const getX = (i: number) => yAxisWidth + padding + i * pointSpacing;

  const tickCount = 5;
  const yTicks = Array.from({ length: tickCount }, (_, i) =>
    paddedMin + (paddedRange * i) / (tickCount - 1)
  ).reverse();

  return (
    <View style={styles.container}>
      {title && <Text style={styles.title}>{title}</Text>}
      {yAxisLabel && <Text style={styles.yAxisLabel}>{yAxisLabel}</Text>}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <Svg width={svgWidth} height={height}>
          <Defs>
            {datasets.map((ds, di) => (
              <LinearGradient
                key={`grad-${di}`}
                id={`area-${di}`}
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <Stop offset="0%" stopColor={ds.color} stopOpacity={0.25} />
                <Stop offset="100%" stopColor={ds.color} stopOpacity={0.02} />
              </LinearGradient>
            ))}
          </Defs>

          {yTicks.map((tick, i) => {
            const y = getY(tick);
            return (
              <G key={`ytick-${i}`}>
                <Line
                  x1={yAxisWidth}
                  y1={y}
                  x2={svgWidth}
                  y2={y}
                  stroke={Colors.light.border}
                  strokeWidth={0.5}
                  strokeDasharray="4,4"
                />
                <SvgText
                  x={yAxisWidth - 4}
                  y={y + 3}
                  fontSize={8}
                  fill={Colors.light.textSecondary}
                  textAnchor="end"
                >
                  {formatValue(tick)}
                </SvgText>
              </G>
            );
          })}

          <Line
            x1={yAxisWidth}
            y1={chartTop + chartH}
            x2={svgWidth}
            y2={chartTop + chartH}
            stroke={Colors.light.border}
            strokeWidth={1}
          />

          {datasets.map((ds, di) => {
            const validPoints = ds.data
              .map((v, i) => ({ v, i }))
              .filter((p) => p.v !== 0);
            if (validPoints.length < 2) return null;

            const pathParts = validPoints.map(
              (p, idx) =>
                `${idx === 0 ? "M" : "L"}${getX(p.i)},${getY(p.v)}`
            );
            const linePath = pathParts.join(" ");

            const areaPath =
              linePath +
              ` L${getX(validPoints[validPoints.length - 1].i)},${chartTop + chartH} L${getX(validPoints[0].i)},${chartTop + chartH} Z`;

            return (
              <G key={di}>
                {showArea && (
                  <Path d={areaPath} fill={`url(#area-${di})`} />
                )}
                <Path
                  d={linePath}
                  fill="none"
                  stroke={ds.color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                />
                {validPoints.map((p) => (
                  <Circle
                    key={`${di}-${p.i}`}
                    cx={getX(p.i)}
                    cy={getY(p.v)}
                    r={3}
                    fill={ds.color}
                  />
                ))}
              </G>
            );
          })}

          {labels.map((label, i) => {
            const showLabel = labels.length <= 12 || i % Math.ceil(labels.length / 10) === 0;
            if (!showLabel) return null;
            return (
              <SvgText
                key={i}
                x={getX(i)}
                y={height - 4}
                fontSize={8}
                fill={Colors.light.textSecondary}
                textAnchor="middle"
              >
                {label}
              </SvgText>
            );
          })}
        </Svg>
      </ScrollView>
      {datasets.length > 1 && (
        <View style={styles.legend}>
          {datasets.map((ds, i) => (
            <View key={i} style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: ds.color }]} />
              <Text style={styles.legendText}>{ds.label}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
  },
  title: {
    fontSize: 14,
    fontFamily: "Inter_600SemiBold",
    color: Colors.light.text,
    marginBottom: 8,
  },
  yAxisLabel: {
    fontSize: 10,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
    marginBottom: 4,
  },
  legend: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginTop: 8,
    gap: 12,
  },
  legendItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legendText: {
    fontSize: 11,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
  },
});

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
  Rect,
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
}

export default function LineChart({
  labels,
  datasets,
  height = 200,
  showArea = false,
  formatValue,
  title,
}: LineChartProps) {
  const chartH = height - 50;
  const padding = 10;
  const screenWidth = Dimensions.get("window").width - 48;
  const pointSpacing = Math.max(40, screenWidth / Math.max(labels.length - 1, 1));
  const svgWidth = Math.max(
    padding * 2 + (labels.length - 1) * pointSpacing,
    screenWidth
  );

  const allValues = datasets.flatMap((ds) => ds.data.filter((v) => v !== 0));
  const maxVal = Math.max(...allValues, 1);
  const minVal = Math.min(...allValues, 0);
  const range = maxVal - minVal || 1;

  const getY = (val: number) => {
    return chartH - ((val - minVal) / range) * (chartH - 20) + 10;
  };
  const getX = (i: number) => padding + i * pointSpacing;

  return (
    <View style={styles.container}>
      {title && <Text style={styles.title}>{title}</Text>}
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
                <Stop offset="0%" stopColor={ds.color} stopOpacity={0.3} />
                <Stop offset="100%" stopColor={ds.color} stopOpacity={0.02} />
              </LinearGradient>
            ))}
          </Defs>

          {[0.25, 0.5, 0.75].map((frac) => {
            const y = getY(minVal + range * frac);
            return (
              <Line
                key={frac}
                x1={0}
                y1={y}
                x2={svgWidth}
                y2={y}
                stroke={Colors.light.border}
                strokeWidth={0.5}
                strokeDasharray="4,4"
              />
            );
          })}

          <Line
            x1={0}
            y1={chartH + 10}
            x2={svgWidth}
            y2={chartH + 10}
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
              ` L${getX(validPoints[validPoints.length - 1].i)},${chartH + 10} L${getX(validPoints[0].i)},${chartH + 10} Z`;

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
            const showLabel = labels.length <= 10 || i % Math.ceil(labels.length / 10) === 0;
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

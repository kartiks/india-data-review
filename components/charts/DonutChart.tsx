import React from "react";
import { View, Text, StyleSheet } from "react-native";
import Svg, { Path, G } from "react-native-svg";
import Colors from "@/constants/colors";

interface DonutChartProps {
  data: Array<{ label: string; value: number; color?: string }>;
  size?: number;
  strokeWidth?: number;
  title?: string;
  formatValue?: (v: number) => string;
  centerLabel?: string;
  centerValue?: string;
}

export default function DonutChart({
  data,
  size = 160,
  strokeWidth = 24,
  title,
  formatValue = (v) => v.toString(),
  centerLabel,
  centerValue,
}: DonutChartProps) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  const radius = (size - strokeWidth) / 2;
  const cx = size / 2;
  const cy = size / 2;

  let cumAngle = -90;

  const arcs = data.map((item, i) => {
    const angle = (item.value / total) * 360;
    const startAngle = cumAngle;
    const endAngle = cumAngle + angle;
    cumAngle = endAngle;

    const startRad = (startAngle * Math.PI) / 180;
    const endRad = (endAngle * Math.PI) / 180;

    const x1 = cx + radius * Math.cos(startRad);
    const y1 = cy + radius * Math.sin(startRad);
    const x2 = cx + radius * Math.cos(endRad);
    const y2 = cy + radius * Math.sin(endRad);

    const largeArc = angle > 180 ? 1 : 0;
    const color =
      item.color || Colors.light.chartColors[i % Colors.light.chartColors.length];

    const d = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`;

    return { d, color, label: item.label, value: item.value, key: i };
  });

  return (
    <View style={styles.container}>
      {title && <Text style={styles.title}>{title}</Text>}
      <View style={styles.chartRow}>
        <View style={styles.svgContainer}>
          <Svg width={size} height={size}>
            <G>
              {arcs.map((arc) => (
                <Path
                  key={arc.key}
                  d={arc.d}
                  fill="none"
                  stroke={arc.color}
                  strokeWidth={strokeWidth}
                  strokeLinecap="round"
                />
              ))}
            </G>
          </Svg>
          {centerLabel && (
            <View style={[styles.centerLabel, { width: size, height: size }]}>
              <Text style={styles.centerValue}>{centerValue}</Text>
              <Text style={styles.centerText}>{centerLabel}</Text>
            </View>
          )}
        </View>
        <View style={styles.legendContainer}>
          {data.map((item, i) => {
            const pct = ((item.value / total) * 100).toFixed(1);
            const color =
              item.color ||
              Colors.light.chartColors[i % Colors.light.chartColors.length];
            return (
              <View key={i} style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: color }]} />
                <View style={styles.legendTextContainer}>
                  <Text style={styles.legendLabel} numberOfLines={1}>
                    {item.label}
                  </Text>
                  <Text style={styles.legendValue}>
                    {pct}%
                  </Text>
                </View>
              </View>
            );
          })}
        </View>
      </View>
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
    marginBottom: 12,
  },
  chartRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
  },
  svgContainer: {
    position: "relative",
  },
  centerLabel: {
    position: "absolute",
    justifyContent: "center",
    alignItems: "center",
  },
  centerValue: {
    fontSize: 16,
    fontFamily: "Inter_700Bold",
    color: Colors.light.text,
  },
  centerText: {
    fontSize: 10,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
  },
  legendContainer: {
    flex: 1,
    gap: 6,
  },
  legendItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legendTextContainer: {
    flex: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  legendLabel: {
    fontSize: 11,
    fontFamily: "Inter_400Regular",
    color: Colors.light.text,
    flex: 1,
  },
  legendValue: {
    fontSize: 11,
    fontFamily: "Inter_600SemiBold",
    color: Colors.light.textSecondary,
    marginLeft: 4,
  },
});

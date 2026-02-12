import React from "react";
import { View, Text, StyleSheet, ScrollView, Dimensions } from "react-native";
import Svg, { Rect, Text as SvgText, Line, G } from "react-native-svg";
import Colors from "@/constants/colors";

interface GroupedBarItem {
  label: string;
  values: Array<{ value: number; color: string; name: string }>;
}

interface GroupedBarChartProps {
  data: GroupedBarItem[];
  height?: number;
  barWidth?: number;
  groupSpacing?: number;
  barGap?: number;
  formatValue?: (v: number) => string;
  title?: string;
  yAxisLabel?: string;
}

function defaultFormat(v: number): string {
  if (Math.abs(v) >= 100000) return `${(v / 100000).toFixed(1)}L`;
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(0)}K`;
  return v.toFixed(0);
}

export default function GroupedBarChart({
  data,
  height = 240,
  barWidth = 14,
  groupSpacing = 18,
  barGap = 2,
  formatValue = defaultFormat,
  title,
  yAxisLabel,
}: GroupedBarChartProps) {
  if (data.length === 0) return null;

  const numBars = data[0]?.values.length || 1;
  const groupWidth = numBars * barWidth + (numBars - 1) * barGap;
  const yAxisW = 42;
  const chartTop = 16;
  const chartBottom = 30;
  const chartH = height - chartTop - chartBottom;

  const allValues = data.flatMap((d) => d.values.map((v) => v.value)).filter((v) => v > 0);
  const maxVal = Math.max(...allValues, 1);

  const totalWidth = yAxisW + data.length * (groupWidth + groupSpacing) + groupSpacing;
  const screenWidth = Dimensions.get("window").width - 48;
  const svgWidth = Math.max(totalWidth, screenWidth);

  const getY = (val: number) => chartTop + chartH - (val / maxVal) * chartH;

  const tickCount = 5;
  const yTicks = Array.from({ length: tickCount }, (_, i) =>
    (maxVal * i) / (tickCount - 1)
  );

  const legendItems = data[0]?.values.map((v) => ({ name: v.name, color: v.color })) || [];

  return (
    <View style={styles.container}>
      {title && <Text style={styles.title}>{title}</Text>}
      {yAxisLabel && <Text style={styles.yAxisLabel}>{yAxisLabel}</Text>}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <Svg width={svgWidth} height={height}>
          {yTicks.map((tick, i) => {
            const y = getY(tick);
            return (
              <G key={`tick-${i}`}>
                <Line
                  x1={yAxisW}
                  y1={y}
                  x2={svgWidth}
                  y2={y}
                  stroke={Colors.light.border}
                  strokeWidth={0.5}
                  strokeDasharray="4,4"
                />
                <SvgText
                  x={yAxisW - 4}
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
            x1={yAxisW}
            y1={chartTop + chartH}
            x2={svgWidth}
            y2={chartTop + chartH}
            stroke={Colors.light.border}
            strokeWidth={1}
          />

          {data.map((group, gi) => {
            const groupX = yAxisW + groupSpacing + gi * (groupWidth + groupSpacing);
            return (
              <G key={gi}>
                {group.values.map((bar, bi) => {
                  if (bar.value <= 0) return null;
                  const x = groupX + bi * (barWidth + barGap);
                  const barH = (bar.value / maxVal) * chartH;
                  const y = chartTop + chartH - barH;
                  return (
                    <Rect
                      key={bi}
                      x={x}
                      y={y}
                      width={barWidth}
                      height={Math.max(barH, 1)}
                      rx={2}
                      fill={bar.color}
                      opacity={0.85}
                    />
                  );
                })}
                <SvgText
                  x={groupX + groupWidth / 2}
                  y={height - 6}
                  fontSize={8}
                  fill={Colors.light.textSecondary}
                  textAnchor="middle"
                >
                  {group.label}
                </SvgText>
              </G>
            );
          })}
        </Svg>
      </ScrollView>
      {legendItems.length > 0 && (
        <View style={styles.legend}>
          {legendItems.map((item, i) => (
            <View key={i} style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: item.color }]} />
              <Text style={styles.legendText}>{item.name}</Text>
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

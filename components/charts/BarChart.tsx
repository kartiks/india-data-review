import React from "react";
import { View, Text, StyleSheet, ScrollView, Dimensions } from "react-native";
import Svg, { Rect, Text as SvgText, Line, G, Path } from "react-native-svg";
import Colors from "@/constants/colors";
import { formatCroreShort } from "@/lib/format";

interface BarChartProps {
  data: Array<{ label: string; value: number; color?: string }>;
  height?: number;
  barWidth?: number;
  spacing?: number;
  showValues?: boolean;
  formatValue?: (v: number) => string;
  title?: string;
  trendlineData?: Array<{ label: string; value: number }>;
  trendlineColor?: string;
  trendlineLabel?: string;
}

export default function BarChart({
  data,
  height = 220,
  barWidth = 28,
  spacing = 12,
  showValues = true,
  formatValue = (v) => v.toString(),
  title,
  trendlineData,
  trendlineColor = Colors.light.textSecondary,
  trendlineLabel,
}: BarChartProps) {
  const hasNegative = data.some((d) => d.value < 0);
  const maxVal = Math.max(...data.map((d) => d.value), 0.1);
  const minVal = Math.min(...data.map((d) => d.value), 0);
  const absMax = Math.max(Math.abs(maxVal), Math.abs(minVal), 0.1);

  const yAxisWidth = 40;
  const chartTop = 16;
  const chartBottom = 28;
  const chartHeight = height - chartTop - chartBottom;
  const totalWidth = data.length * (barWidth + spacing) + spacing + yAxisWidth;
  const screenWidth = Dimensions.get("window").width - 48;
  const svgWidth = Math.max(totalWidth, screenWidth);

  let zeroY: number;
  let getBarY: (val: number) => { y: number; h: number };

  if (hasNegative) {
    const range = maxVal - minVal || 1;
    zeroY = chartTop + ((maxVal) / range) * chartHeight;

    getBarY = (val: number) => {
      if (val >= 0) {
        const h = (val / range) * chartHeight;
        return { y: zeroY - h, h };
      } else {
        const h = (Math.abs(val) / range) * chartHeight;
        return { y: zeroY, h };
      }
    };
  } else {
    zeroY = chartTop + chartHeight;
    getBarY = (val: number) => {
      const h = (val / absMax) * chartHeight;
      return { y: zeroY - h, h };
    };
  }

  const yTicks = hasNegative
    ? [maxVal, maxVal * 0.5, 0, minVal * 0.5, minVal].filter((v, i, arr) => arr.indexOf(v) === i)
    : [0, absMax * 0.25, absMax * 0.5, absMax * 0.75, absMax];

  const getYPos = (val: number) => {
    if (hasNegative) {
      const range = maxVal - minVal || 1;
      return chartTop + ((maxVal - val) / range) * chartHeight;
    }
    return zeroY - (val / absMax) * chartHeight;
  };

  return (
    <View style={styles.container}>
      {title && <Text style={styles.title}>{title}</Text>}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <Svg width={svgWidth} height={height}>
          {yTicks.map((tick, i) => {
            const y = getYPos(tick);
            return (
              <G key={`tick-${i}`}>
                <Line
                  x1={yAxisWidth}
                  y1={y}
                  x2={svgWidth}
                  y2={y}
                  stroke={tick === 0 && hasNegative ? Colors.light.text + "30" : Colors.light.border}
                  strokeWidth={tick === 0 && hasNegative ? 1.5 : 0.5}
                  strokeDasharray={tick === 0 ? undefined : "4,4"}
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

          {data.map((item, i) => {
            const { y, h } = getBarY(item.value);
            const x = yAxisWidth + spacing + i * (barWidth + spacing);
            const color = item.color || Colors.light.chartColors[i % Colors.light.chartColors.length];
            return (
              <G key={i}>
                <Rect
                  x={x}
                  y={y}
                  width={barWidth}
                  height={Math.max(h, 1)}
                  rx={3}
                  fill={color}
                  opacity={0.85}
                />
                {showValues && Math.abs(item.value) > 0 && (
                  <SvgText
                    x={x + barWidth / 2}
                    y={item.value >= 0 ? y - 4 : y + h + 12}
                    fontSize={8}
                    fill={Colors.light.textSecondary}
                    textAnchor="middle"
                    fontWeight="600"
                  >
                    {formatValue(item.value)}
                  </SvgText>
                )}
                <SvgText
                  x={x + barWidth / 2}
                  y={height - 4}
                  fontSize={8}
                  fill={Colors.light.textSecondary}
                  textAnchor="middle"
                >
                  {item.label}
                </SvgText>
              </G>
            );
          })}

          {trendlineData && trendlineData.length > 1 && (() => {
            const trendMax = Math.max(...trendlineData.map(d => d.value), 0.1);
            const trendMin = Math.min(...trendlineData.map(d => d.value), 0);
            const points = trendlineData.map((d, i) => {
              const x = yAxisWidth + spacing + i * (barWidth + spacing) + barWidth / 2;
              const yPos = getYPos(d.value);
              return `${i === 0 ? "M" : "L"}${x},${yPos}`;
            });
            return (
              <G>
                <Path
                  d={points.join(" ")}
                  fill="none"
                  stroke={trendlineColor}
                  strokeWidth={2}
                  strokeDasharray="6,3"
                  opacity={0.7}
                />
                {trendlineData.map((d, i) => {
                  const x = yAxisWidth + spacing + i * (barWidth + spacing) + barWidth / 2;
                  const yPos = getYPos(d.value);
                  return (
                    <G key={`trend-${i}`}>
                      <Rect x={x - 2.5} y={yPos - 2.5} width={5} height={5} rx={1} fill={trendlineColor} />
                    </G>
                  );
                })}
              </G>
            );
          })()}
        </Svg>
      </ScrollView>
      {trendlineLabel && (
        <View style={styles.trendLegend}>
          <View style={[styles.trendLine, { backgroundColor: trendlineColor }]} />
          <Text style={styles.trendLegendText}>{trendlineLabel}</Text>
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
  trendLegend: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 6,
  },
  trendLine: {
    width: 16,
    height: 2,
    borderRadius: 1,
  },
  trendLegendText: {
    fontSize: 10,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
  },
});
